from oddslingers.tests.test_utils import MonkeyPatch
from oddslingers.utils import DoesNothing

from poker.controllers import (HoldemFreezeoutController, InvalidAction,
                               BountyFreezeoutController)
from poker.constants import (PlayingState, Event, Action, NL_BOUNTY,
                             BOUNTY_TOURNEY_BBS_TO_CALL)
from poker.models import Freezeout
from poker.subscribers import BankerSubscriber

from poker.tests.test_controller import TableWithChipsTest


class FreezeoutControllerTest(TableWithChipsTest):
    def setUp(self):
        super().setUp()
        for plyr in self.accessor.players:
            plyr.stack = 5000

        self.table.tournament = Freezeout.objects.create_tournament(name='test')
        for player in self.players:
            self.table.tournament.entrants.add(player.user)

        self.controller = HoldemFreezeoutController(
            self.table, self.players,
            log=DoesNothing(), subscribers=[]#, verbose=True
        )
        self.accessor = self.controller.accessor
        self.controller.commit()


class BlindsScheduleTest(FreezeoutControllerTest):
    def test_blinds_schedule(self):
        self.controller.step()
        first_bb_size = self.accessor.players_at_position(
            self.table.bb_idx, active_only=True
        ).wagers
        # blinds should increase by hand 100
        for _ in range(100):
            next_plyr = self.controller.accessor.next_to_act()
            self.controller.dispatch('FOLD', player_id=next_plyr.id)

        new_bb_size = self.accessor.players_at_position(
            self.table.bb_idx, active_only=True
        ).wagers

        assert first_bb_size < new_bb_size


class TourneySitOutTest(FreezeoutControllerTest):
    def test_dont_get_booted_and_get_cards(self):
        self.controller.step()
        sb_plyr = self.accessor.players_at_position(
            self.table.sb_idx, active_only=True
        )
        self.controller.dispatch('SIT_OUT', player_id=sb_plyr.id)

        assert sb_plyr.playing_state == PlayingState.TOURNEY_SITTING_OUT
        assert sb_plyr.cards

        for _ in range(100):
            next_plyr = self.controller.accessor.next_to_act()
            self.controller.dispatch('FOLD', player_id=next_plyr.id)

        assert sb_plyr.seated
        assert sb_plyr.cards

    def test_sit_in_out_toggle(self):
        self.controller.step()
        next_plyr = self.accessor.next_to_act()
        self.controller.dispatch('SIT_OUT', player_id=next_plyr.id)

        # sitting out causes you to auto-folding
        assert next_plyr.last_action == Event.FOLD
        assert next_plyr.playing_state == PlayingState.TOURNEY_SITTING_OUT

        self.controller.dispatch('SIT_IN', player_id=next_plyr.id)
        assert next_plyr.playing_state == PlayingState.SITTING_IN

        with self.assertRaises(InvalidAction):
            self.controller.dispatch('SIT_IN', player_id=next_plyr.id)

        self.controller.dispatch('SIT_OUT', player_id=next_plyr.id)
        assert next_plyr.playing_state == PlayingState.TOURNEY_SITTING_OUT

        self.controller.dispatch('SIT_IN', player_id=next_plyr.id)
        assert next_plyr.playing_state == PlayingState.SITTING_IN

    def test_toggling_autofolding_doesnt_skip_turns(self):
        self.setup_hand(blinds_positions={
            'btn_pos': 0,  # pirate
            'sb_pos': 1,  # cuttlefish
            'bb_pos': 2,  # ajfenix
        })
        self.ajfenix_player.seated = False
        self.ajfenix_player.playing_state = None
        self.cuttlefish_player.seated = False
        self.cuttlefish_player.playing_state = None

        assert self.accessor.heads_up()
        assert self.accessor.next_to_act() == self.cowpig_player

        # Toggling autofold
        self.controller.dispatch('SIT_OUT',
                                 player_id=self.pirate_player.id)
        assert self.accessor.next_to_act() == self.cowpig_player
        self.controller.dispatch('SIT_IN',
                                 player_id=self.pirate_player.id)
        assert self.accessor.next_to_act() == self.cowpig_player
        self.controller.dispatch('SIT_OUT',
                                 player_id=self.pirate_player.id)
        assert self.accessor.next_to_act() == self.cowpig_player
        self.controller.dispatch('SIT_IN',
                                 player_id=self.pirate_player.id)
        assert self.accessor.next_to_act() == self.cowpig_player

        # Acting with the next to act
        self.controller.dispatch('CHECK',
                                 player_id=self.cowpig_player.id)

        # Next to act should be pirate, it shouldn't skip his turn
        assert self.accessor.next_to_act() == self.pirate_player

    def test_timeout_fold_sits_out(self):
        self.setup_hand(blinds_positions={
            'btn_pos': 0,  # pirate
            'sb_pos': 1,  # cuttlefish
            'bb_pos': 2,  # ajfenix
        })
        cowpig = self.cowpig_player

        yes_out_of_time = lambda self, player: True
        acc_klass = self.accessor.__class__
        with MonkeyPatch(acc_klass, 'is_out_of_time', yes_out_of_time):
            self.controller.timed_dispatch()

            assert cowpig.last_action == Event.SIT_OUT
            assert cowpig.playing_state == PlayingState.TOURNEY_SITTING_OUT

    def test_sitout_player_autofolds_except_first_to_act(self):
        self.setup_hand(blinds_positions={
            'btn_pos': 0,  # pirate
            'sb_pos': 1,  # cuttlefish
            'bb_pos': 2,  # ajfenix
        })

        assert self.accessor.next_to_act() == self.cowpig_player

        self.controller.dispatch('SIT_OUT',
                                 player_id=self.pirate_player.id)
        assert self.accessor.next_to_act() == self.cowpig_player

        self.controller.dispatch('SIT_OUT',
                                 player_id=self.cowpig_player.id)
        # cowpig sits out & folds; autofolds pirate
        assert self.cowpig_player.last_action == Event.FOLD
        assert self.pirate_player.last_action == Event.FOLD
        assert self.accessor.next_to_act() == self.cuttlefish_player

        self.controller.dispatch('SIT_OUT',
                                 player_id=self.ajfenix_player.id)
        assert self.accessor.next_to_act() == self.cuttlefish_player

        self.controller.dispatch('CALL',
                                 player_id=self.cuttlefish_player.id)

        # cuttlefish calls, and then ajfenix auto-folds
        # in next hand, pirate is sitting out, so he's not going to autofold
        # because he's the first to act
        assert self.accessor.next_to_act() == self.pirate_player
        assert self.pirate_player.last_action is None
        # Pirate is in his delay period on which he can choose to do any action
        # Or sit in back again, just for testing purposes, let's fold.
        self.controller.dispatch('FOLD', player_id=self.pirate_player.id)

        # It's cuttlefish's turn and he is sit in so he can act as he wishes
        self.controller.dispatch('CALL',
                                 player_id=self.cuttlefish_player.id)

        # Then, because ajfenix and cowpig are sitting out and they are not first
        # to act, they will auto-fold, so cuttlefish wins and will be first to
        # act in next hand
        assert self.accessor.next_to_act() == self.cuttlefish_player


class TourneyAutoRebuyInactiveTest(FreezeoutControllerTest):
    def test_tourney_auto_rebuy_inactive(self):
        self.pirate_player.auto_rebuy = 10000

        self.controller.step()
        for _ in range(5):
            next_plyr = self.controller.accessor.next_to_act()
            self.controller.dispatch('FOLD', player_id=next_plyr.id)

        assert self.pirate_player.stack <= 5000


class TourneyBootWhenStackedTest(FreezeoutControllerTest):
    def test_tourney_boot_when_stacked(self):
        self.setup_hand(
            blinds_positions={
                'btn_pos': 0,  # pirate
                'sb_pos': 1,  # cuttlefish
                'bb_pos': 2,  # ajfenix
            },
            player_hole_cards={
                self.pirate_player:     'Kc,Kd',
                self.cuttlefish_player: '2c,3d',
                self.ajfenix_player:    '4c,5d',
                self.cowpig_player:     'Ac,Ad',
            },
            board_str='2h,4h,7d,9c,Jh'
        )
        self.controller.dispatch('RAISE_TO',
                                 player_id=self.cowpig_player.id,
                                 amt=5000)
        self.controller.dispatch('CALL',
                                 player_id=self.pirate_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.ajfenix_player.id)

        assert not self.pirate_player.seated


class TourneyActionsTest(FreezeoutControllerTest):
    def test_tourney_actions(self):
        self.setup_hand(
            blinds_positions={
                'btn_pos': 0,  # pirate
                'sb_pos': 1,  # cuttlefish
                'bb_pos': 2,  # ajfenix
            },
            player_hole_cards={
                self.pirate_player:     'Kc,Kd',
                self.cuttlefish_player: '2c,3d',
                self.ajfenix_player:    '4c,5d',
                self.cowpig_player:     'Ac,Ad',
            },
            board_str='2h,4h,7d,9c,Jh'
        )
        self.controller.step()
        next_to_act = self.accessor.next_to_act()
        avail_acts = self.accessor.available_actions(next_to_act)

        assert Action.BUY not in avail_acts
        assert Action.LEAVE_SEAT not in avail_acts
        assert Action.SIT_OUT_AT_BLINDS not in avail_acts
        assert Action.SET_AUTO_REBUY not in avail_acts

        self.controller.dispatch('RAISE_TO',
                                 player_id=self.cowpig_player.id,
                                 amt=5000)
        self.controller.dispatch('CALL',
                                 player_id=self.pirate_player.id)
        self.controller.dispatch('SIT_OUT',
                                 player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.ajfenix_player.id)

        avail_acts = self.accessor.available_actions(self.pirate_player)
        assert Action.TAKE_SEAT not in avail_acts

        avail_acts = self.accessor.available_actions(self.cuttlefish_player)
        assert Action.SIT_IN_AT_BLINDS not in avail_acts

    def test_is_acting_first(self):
        self.setup_hand(blinds_positions={
            'btn_pos': 0,  # pirate
            'sb_pos': 1,  # cuttlefish
            'bb_pos': 2,  # ajfenix
        })

        assert self.accessor.next_to_act() == self.cowpig_player
        assert self.cowpig_player.last_action == None
        assert self.accessor.is_acting_first(self.cowpig_player)
        assert not self.accessor.heads_up()

    def test_is_acting_first_heads_up(self):
        self.pirate_player.seated = False
        self.cuttlefish_player.seated = False

        self.table.btn_idx = 3 # cowpig

        self.controller.step()

        assert self.accessor.heads_up()
        assert self.accessor.next_to_act() == self.cowpig_player
        assert self.cowpig_player.last_action == Event.POST
        assert self.accessor.is_acting_first(self.cowpig_player)


class TournamentFinishingTest(FreezeoutControllerTest):
    def test_tournament_finish(self):
        self.controller.subscribers = [
            BankerSubscriber(self.accessor)
        ]
        self.setup_hand(
            blinds_positions={
                'btn_pos': 0,  # pirate
                'sb_pos': 1,  # cuttlefish
                'bb_pos': 2,  # ajfenix
            },
            player_hole_cards={
                self.pirate_player:     'Kc,Kd',
                self.cuttlefish_player: '2c,3d',
                self.ajfenix_player:    '4c,5d',
                self.cowpig_player:     'Ac,Ad',
            },
            board_str='2h,4h,7d,9c,Jh'
        )
        self.controller.dispatch('RAISE_TO',
                                 player_id=self.cowpig_player.id,
                                 amt=5000)
        self.controller.dispatch('CALL',
                                 player_id=self.pirate_player.id)
        self.controller.dispatch('CALL',
                                 player_id=self.cuttlefish_player.id)
        self.controller.dispatch('CALL',
                                 player_id=self.ajfenix_player.id)

        assert not self.pirate_player.seated
        assert not self.cuttlefish_player.seated
        assert not self.ajfenix_player.seated

        tourney = self.table.tournament
        assert tourney.get_status_display() == 'FINISHED'

        # Adding 1000 chips because TableWithChipsTest already adds 1000
        self.cowpig.userbalance().refresh_from_db()
        assert self.cowpig.userbalance().balance \
               == (tourney.buyin_amt * tourney.entrants.count()) + 1000

        # Assert that the winner (cowpig) doesn't have chips in play
        assert self.cowpig.chips_in_play == 0


class TestBountyTournament(FreezeoutControllerTest):
    def test_bounty_win(self):
        self.table.table_type = NL_BOUNTY
        self.controller = BountyFreezeoutController(
            self.table, self.players,
            log=DoesNothing(), subscribers=[]#, verbose=True
        )
        self.accessor = self.controller.accessor
        self.controller.commit()

        self.setup_hand(
            blinds_positions={
                'btn_pos': 0,  # pirate
                'sb_pos': 1,  # cuttlefish
                'bb_pos': 2,  # ajfenix
            },
            player_hole_cards={
                self.pirate_player:     'Kc,Kd',
                self.cuttlefish_player: '2c,3d',
                self.ajfenix_player:    '4c,5d',
                self.cowpig_player:     '7s,2d',
            },
            board_str='2h,4h,7d,9c,Jh'
        )

        self.controller.dispatch('CALL',
                                 player_id=self.cowpig_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.pirate_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.ajfenix_player.id)

        assert self.accessor.table.bounty_flag
        assert (self.accessor.current_pot()
                == self.table.bb * BOUNTY_TOURNEY_BBS_TO_CALL * 3)
