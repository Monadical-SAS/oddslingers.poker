from datetime import timedelta
from decimal import Decimal
from django.utils import timezone

from oddslingers.tests.test_utils import TimezoneMocker
from oddslingers.subscribers import UserStatsSubscriber
from oddslingers.mutations import execute_mutations

from poker.subscribers import (
    ChatSubscriber, AnimationSubscriber,
    TableStatsSubscriber, LogSubscriber,
    TournamentResultsSubscriber, LevelSubscriber,
    BankerSubscriber
)
from poker.tests.test_controller import GenericTableTest
from poker.tests.test_freezeout import FreezeoutControllerTest
from poker.bots import get_robot_move
from poker.megaphone import gamestate_json
from poker.handhistory import DBLog
from poker.constants import (
    HAND_SAMPLING_CAP, PlayingState, CASH_GAME_BBS, N_BB_TO_NEXT_LEVEL,
    CASHTABLES_LEVELUP_BONUS
)
from poker.models import TournamentResult, PokerTable, Player
from poker.level_utils import update_levels, earned_chips

from banker.mutations import buy_chips, transfer_chips
from banker.utils import balance


class FoldNotSentTwiceBySubscriberTest(GenericTableTest):
    def test_fold_not_sent_twice(self):
        chatsub = ChatSubscriber(self.controller.accessor)
        self.controller.subscribers = [chatsub]
        self.table.seconds_per_action_base = 0
        self.table.min_timebank = 0
        self.table.max_timebank = 0
        self.table.save()
        self.table.player_set.update(timebank_remaining=0)
        self.table.player_set.update(n_hands_played=15000)

        for player in self.controller.accessor.players:
            player.refresh_from_db()

        self.controller.step()
        self.controller.timed_dispatch()

        assert sum(
            'fold' in chat['message']
            for chat in chatsub.to_broadcast['all']['chat']
        ) == 1


class AnimationPatchesTest(GenericTableTest):
    def test_anim_patch_privacy(self):
        anim_sub = AnimationSubscriber(self.controller.accessor)
        self.controller.subscribers = [anim_sub]
        self.controller.step()

        for _ in range(10):
            action, kwargs = get_robot_move(
                self.accessor,
                self.controller.log,
                delay=False,
                stupid=True,
                warnings=False
            )

            self.controller.dispatch(action, **kwargs)

            for player in self.controller.accessor.active_players():
                updates = str(anim_sub.updates_for_broadcast(player))
                assert '_PRIVATE_' not in updates

            assert '_PRIVATE_' not in str(anim_sub.updates_for_broadcast())

            # test that RESET events have empty card patches
            for anim in anim_sub.to_broadcast:
                if anim['type'] == 'RESET':
                    for patch in anim['patches']:
                        if 'card' in patch['path']:
                            assert not patch['value']

            # anims = anim_sub.updates_for_broadcast()


class AnimationsAppearTest(GenericTableTest):
    def test_animations(self):
        anim_sub = AnimationSubscriber(self.controller.accessor)
        self.controller.subscribers = [anim_sub]
        self.controller.step()
        nxt = self.controller.accessor.next_to_act()
        self.controller.player_dispatch('FOLD', player_id=nxt.id)
        self.controller.commit()

        gamestate = gamestate_json(self.controller.accessor,
                                   subscribers=self.controller.subscribers)

        assert len(gamestate['animations']) > 1
        assert isinstance(gamestate['animations'][0], dict)


class TableStatsSubscriberTest(GenericTableTest):
    def test_players_per_flop_pct(self):
        """
        Tests if the players_per_flop_pct value is being
        calculated correctly
        """
        self.stats_sub = TableStatsSubscriber(self.accessor)
        self.controller.subscribers.append(self.stats_sub)
        self.controller.step()
        self.controller.dispatch(
            'RAISE_TO',
            player_id=self.accessor.next_to_act().id,
            amt=20
        )
        for _ in range(len(self.players) - 1):
            p = self.accessor.next_to_act()
            self.controller.dispatch('CALL', player_id=p.id)
        table_stats = self.stats_sub.updates_for_broadcast()['table_stats']
        calculated_ppf = table_stats['players_per_flop_pct']
        assert calculated_ppf == 100

    def test_ppf_pct_at_endhand_preflop(self):
        """
        Tests if the players_per_flop_pct value is being calculated
        correctly for the case in which everybody folded on preflop
        """
        self.stats_sub = TableStatsSubscriber(self.accessor)
        starting_pct_players = 50
        starting_n_samples = 10
        self.stats_sub.table_stats.players_per_flop_pct = starting_pct_players
        self.stats_sub.table_stats.num_samples = starting_n_samples
        self.controller.subscribers.append(self.stats_sub)
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2
        self.controller.step()
        self.controller.dispatch(
            'RAISE_TO',
            player_id=self.pirate_player.id,
            amt=40
        )
        self.controller.dispatch('FOLD', player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD', player_id=self.ajfenix_player.id)
        self.controller.dispatch('FOLD', player_id=self.cowpig_player.id)

        table_stats = self.stats_sub.updates_for_broadcast()['table_stats']
        calculated_ppf = table_stats['players_per_flop_pct']
        expected_ppf = (starting_n_samples * starting_pct_players + 0) \
                     / (starting_n_samples + 1)
        assert calculated_ppf == expected_ppf

    def test_avg_stack(self):
        """
        Tests if the avg_stack value is being calculated correctly
        """
        self.stats_sub = TableStatsSubscriber(self.accessor)
        self.stats_sub.table_stats.players_per_flop_pct = 50
        self.stats_sub.table_stats.num_samples = 10
        self.controller.subscribers.append(self.stats_sub)
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2
        self.controller.step()
        self.controller.dispatch(
            'RAISE_TO',
            player_id=self.pirate_player.id,
            amt=40
        )
        table_stats = self.stats_sub.updates_for_broadcast()['table_stats']
        calculated_avg_stack = table_stats['avg_stack']
        assert calculated_avg_stack == 250

    def test_avg_pot(self):
        """
        Tests if the avg_pot value is being calculated correctly
        """
        self.stats_sub = TableStatsSubscriber(self.accessor)
        self.controller.subscribers.append(self.stats_sub)
        self.controller.step()

        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='RAISE_TO', amt=50)
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CALL')
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CALL')
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CALL')

        self.accessor.table.board = ['3h', '3c', '4h', '5h', 'Kd']
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CHECK')
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CHECK')
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CHECK')

        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CHECK')
        table_stats = self.stats_sub.updates_for_broadcast()['table_stats']
        calculated_avg_pot = table_stats['avg_pot']
        assert calculated_avg_pot == 200

    def _simulate_n_hands_over_time(self,
                                    n_hands,
                                    sim_elapsed_mins,
                                    mins_per_hand):
        self.stats_sub = TableStatsSubscriber(self.accessor)
        self.controller.log = DBLog(self.accessor)
        log_subscriber = LogSubscriber(self.controller.log)
        self.controller.subscribers = [self.stats_sub, log_subscriber]
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2

        self.controller.step()
        self.controller.commit()

        start_time = timezone.now()

        for hand_simulation_index in range(1, n_hands + 1):
            mins_offset = hand_simulation_index * mins_per_hand

            in_a_few = timedelta(minutes=mins_offset)
            with TimezoneMocker(start_time + in_a_few) as t:
                self.controller.dispatch(
                    'CALL',
                    player_id=self.accessor.next_to_act().id
                )
                # multiple actions on a table with the same timestamp
                #   are blocked so we must bump the time by a tiny
                #   amount between actions
                t.bump_time()
                self.controller.dispatch(
                    'FOLD',
                    player_id=self.accessor.next_to_act().id
                )
                t.bump_time()
                self.controller.dispatch(
                    'FOLD',
                    player_id=self.accessor.next_to_act().id
                )
                t.bump_time()
                self.controller.dispatch(
                    'FOLD',
                    player_id=self.accessor.next_to_act().id
                )

    def test_hands_per_hour_with_30hands_in_120mins(self):
        n_hands = HAND_SAMPLING_CAP + 10  # 30 hands
        sim_elapsed_mins = 120
        mins_per_hand = sim_elapsed_mins / n_hands  # 4 mins

        self._simulate_n_hands_over_time(
            n_hands=n_hands,
            sim_elapsed_mins=sim_elapsed_mins,
            mins_per_hand=mins_per_hand
        )

        table_stats = self.stats_sub.updates_for_broadcast()['table_stats']
        calculated_hands_per_hour = table_stats['hands_per_hour']
        # The elapsed hours are calculated using the HAND_SAMPLING_CAP
        # because the n_hands is bigger than it.
        num_hands = HAND_SAMPLING_CAP
        # Adding one because we need to handle the case when exactly
        # 'HAND_SAMPLING_CAP' had being played
        elapsed_hours = ((num_hands + 1) * mins_per_hand) / 60
        expected_hands_per_hour = round(num_hands / elapsed_hours, 2)
        assert calculated_hands_per_hour == expected_hands_per_hour
        # Check the samples number are capped at HAND_SAMPLING_CAP
        #   after n_hands
        assert table_stats['num_samples'] == HAND_SAMPLING_CAP

    def test_hands_per_hour_with_10hands_in_120mins(self):
        n_hands = 10
        sim_elapsed_mins = 120
        mins_per_hand = sim_elapsed_mins / n_hands  # 12 mins

        self._simulate_n_hands_over_time(
            n_hands=n_hands,
            sim_elapsed_mins=sim_elapsed_mins,
            mins_per_hand=mins_per_hand
        )

        table_stats = self.stats_sub.updates_for_broadcast()['table_stats']
        calculated_hands_per_hour = table_stats['hands_per_hour']
        elapsed_hours = (n_hands * mins_per_hand) / 60
        expected_hands_per_hour = round(n_hands / elapsed_hours, 2)
        assert calculated_hands_per_hour == expected_hands_per_hour

    def test_hands_per_hour_with_1hand_in_120mins(self):
        n_hands = 1
        sim_elapsed_mins = 120
        mins_per_hand = 10  # it doesn't matter for this test

        self._simulate_n_hands_over_time(
            n_hands=n_hands,
            sim_elapsed_mins=sim_elapsed_mins,
            mins_per_hand=mins_per_hand
        )

        table_stats = self.stats_sub.updates_for_broadcast()['table_stats']
        calculated_hands_per_hour = table_stats['hands_per_hour']
        elapsed_hours = (n_hands * mins_per_hand) / 60
        expected_hands_per_hour = round(n_hands / elapsed_hours, 2)
        assert calculated_hands_per_hour == expected_hands_per_hour

    def test_not_enough_players_to_play(self):
        self.stats_sub = TableStatsSubscriber(self.accessor)
        self.controller.subscribers = [self.stats_sub]
        self.pirate_player.playing_state = PlayingState.SITTING_OUT
        self.cuttlefish_player.playing_state = PlayingState.SITTING_OUT
        self.ajfenix_player.playing_state = PlayingState.SITTING_OUT
        self.cowpig_player.playing_state = PlayingState.SITTING_OUT
        self.controller.step()
        table_stats = self.stats_sub.updates_for_broadcast()['table_stats']
        assert table_stats is None


class TournamentResultsSubscriberTest(FreezeoutControllerTest):
    def setUp(self):
        super().setUp()
        self.results_sub = TournamentResultsSubscriber(self.accessor)
        self.controller.subscribers = [self.results_sub]

    def test_results_on_players_booting(self):
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

        assert TournamentResult.objects.get(
            tournament=self.table.tournament,
            user=self.cowpig_player.user
        ).placement == 1
        assert TournamentResult.objects.get(
            tournament=self.table.tournament,
            user=self.ajfenix_player.user
        ).placement == 2
        assert TournamentResult.objects.get(
            tournament=self.table.tournament,
            user=self.cuttlefish_player.user
        ).placement == 3
        assert TournamentResult.objects.get(
            tournament=self.table.tournament,
            user=self.pirate_player.user
        ).placement == 4


class LevelUpTest(GenericTableTest):
    def test_levelup(self):
        level = self.cuttlefish.games_level_number
        next_level = level + 1
        next_level_chips = Decimal(
            CASH_GAME_BBS[next_level - 1] * N_BB_TO_NEXT_LEVEL / 2
        )
        self.pirate_player.stack = next_level_chips
        self.cuttlefish_player.stack = next_level_chips
        self.controller.subscribers = [
            LevelSubscriber(self.accessor),
            BankerSubscriber(self.accessor),
        ]

        self.setup_hand(
            blinds_positions={
                'btn_pos': 1,
                'sb_pos': 2,
                'bb_pos': 3,
            },
            player_hole_cards={
                self.pirate_player: '2s,3s',
                self.cuttlefish_player: 'Qh,Ac',
                self.ajfenix_player: '2c,8d',
                self.cowpig_player: '3d,Th'
            },
            board_str='As,Ad,Qd,6s,7s',
        )

        assert self.cuttlefish.cashtables_level == CASH_GAME_BBS[level - 1]

        pirate_level = self.pirate.games_level_number
        old_pirate_cashtables_level = self.pirate.cashtables_level
        assert old_pirate_cashtables_level == CASH_GAME_BBS[pirate_level - 1]

        self.controller.dispatch(
            'RAISE_TO',
            player_id=self.pirate_player.id,
            amt=self.pirate_player.stack
        )
        self.controller.dispatch('CALL', player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD', player_id=self.ajfenix_player.id)
        self.controller.dispatch('FOLD', player_id=self.cowpig_player.id)

        assert self.pirate.cashtables_level == old_pirate_cashtables_level

        self.cuttlefish.userstats().refresh_from_db()
        del self.cuttlefish.games_level # delete cached property
        assert self.cuttlefish.cashtables_level == CASH_GAME_BBS[next_level - 1]

    def test_transfers_dont_levelup(self):
        curr_earned_chips = earned_chips(self.pirate)
        execute_mutations(
            buy_chips(self.cowpig, 10000)
        )
        assert self.pirate.userbalance().balance == 0
        assert self.pirate.cashtables_level == CASH_GAME_BBS[0]
        execute_mutations(
            transfer_chips(self.cowpig, self.pirate, 10000)
        )
        assert self.pirate.userbalance().balance == 10000
        assert earned_chips(self.pirate) == curr_earned_chips
        assert self.pirate.cashtables_level == CASH_GAME_BBS[0]


class LevelDownTest(GenericTableTest):
    def test_level_aint_go_down(self):
        level_no_drop = CASH_GAME_BBS[2]

        cuttlefish_stats = self.cuttlefish.userstats()
        cuttlefish_stats.games_level = level_no_drop * N_BB_TO_NEXT_LEVEL
        cuttlefish_stats.save()

        self.controller.subscribers = [
            LevelSubscriber(self.accessor),
            BankerSubscriber(self.accessor),
        ]

        self.setup_hand(
            blinds_positions={
                'btn_pos': 1,
                'sb_pos': 2,
                'bb_pos': 3,
            },
            player_hole_cards={
                self.pirate_player: '2s,3s',
                self.cuttlefish_player: 'Qh,Ac',
                self.ajfenix_player: '2c,8d',
                self.cowpig_player: '3d,Th'
            },
            board_str='As,Ad,Qd,6s,7s',
        )
        self.controller.dispatch(
            'RAISE_TO',
            player_id=self.pirate_player.id,
            amt=self.pirate_player.stack
        )
        self.controller.dispatch('CALL', player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD', player_id=self.ajfenix_player.id)
        self.controller.dispatch('FOLD', player_id=self.cowpig_player.id)

        self.cuttlefish.userbalance().refresh_from_db()
        assert self.cuttlefish.userbalance().balance == 0
        assert earned_chips(self.cuttlefish) == 0
        assert self.cuttlefish.cashtables_level == level_no_drop

        mutations, _ = update_levels(self.cuttlefish)
        execute_mutations(mutations)

        assert self.cuttlefish.cashtables_level == level_no_drop


class LevelUpChipsInPlayNoBalanceTest(GenericTableTest):
    def test_levelup_with_no_balance(self):
        self.cuttlefish.userbalance().refresh_from_db()
        assert self.cuttlefish.userbalance().balance == 0
        assert self.cuttlefish.cashtables_level == CASH_GAME_BBS[0]

        self.table_2 = PokerTable.objects.create_table(
            name="test_table_2"
        )
        self.cuttlefish_player_2 = Player.objects.create(
            user=self.cuttlefish,
            stack=Decimal(CASH_GAME_BBS[1] * N_BB_TO_NEXT_LEVEL),
            table=self.table_2,
            position=1,
            seated=True,
            playing_state=PlayingState.SITTING_IN,
        )

        self.controller.subscribers = [
            LevelSubscriber(self.accessor),
            BankerSubscriber(self.accessor),
        ]

        self.setup_hand(
            blinds_positions={
                'btn_pos': 1,
                'sb_pos': 2,
                'bb_pos': 3,
            },
            player_hole_cards={
                self.pirate_player: '2s,3s',
                self.cuttlefish_player: 'Qh,Ac',
                self.ajfenix_player: '2c,8d',
                self.cowpig_player: '3d,Th'
            },
            board_str='As,Ad,Qd,6s,7s',
        )
        self.controller.dispatch(
            'RAISE_TO',
            player_id=self.pirate_player.id,
            amt=self.pirate_player.stack
        )
        self.controller.dispatch('CALL', player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD', player_id=self.ajfenix_player.id)
        self.controller.dispatch('FOLD', player_id=self.cowpig_player.id)

        self.cuttlefish.userbalance().refresh_from_db()
        new_balance = self.cuttlefish.userbalance().balance
        assert new_balance == CASHTABLES_LEVELUP_BONUS * CASH_GAME_BBS[1]

        self.cuttlefish.userstats().refresh_from_db()
        del self.cuttlefish.games_level # delete cached property
        assert self.cuttlefish.cashtables_level == CASH_GAME_BBS[1]

        #assert new_balance == earned_chips(self.cuttlefish)


class UpdateLevelsTest(GenericTableTest):
    def test_update_levels(self):
        self.pirate.userbalance().refresh_from_db()
        assert self.pirate.userbalance().balance == 0
        assert earned_chips(self.pirate) == 0
        assert self.pirate.cashtables_level == CASH_GAME_BBS[0]

        next_level_cash = N_BB_TO_NEXT_LEVEL * CASH_GAME_BBS[1]

        execute_mutations(
            buy_chips(self.pirate, next_level_cash)
        )

        self.pirate.userbalance().refresh_from_db()
        assert self.pirate.userbalance().balance == next_level_cash
        assert earned_chips(self.pirate) == next_level_cash

        assert self.pirate.cashtables_level == CASH_GAME_BBS[0]

        mutations, _ = update_levels(self.pirate)
        execute_mutations(mutations)

        self.pirate.userstats().refresh_from_db()

        del self.pirate.games_level # delete cached property
        assert self.pirate.cashtables_level == CASH_GAME_BBS[1]
        new_balance = self.pirate.userbalance().balance
        assert new_balance > next_level_cash
        assert new_balance == earned_chips(self.pirate)


class MultipleLevelsBumpTest(GenericTableTest):
    def test_multiple_levels_bump(self):
        level_three_chips = N_BB_TO_NEXT_LEVEL * CASH_GAME_BBS[2]
        self.pirate_player.stack = level_three_chips - 1
        self.cuttlefish_player.stack = level_three_chips - 1

        self.controller.subscribers = [
            LevelSubscriber(self.accessor),
            BankerSubscriber(self.accessor),
        ]

        self.setup_hand(blinds_positions={
            'btn_pos': 1,
            'sb_pos': 2,
            'bb_pos': 3,
        })

        assert balance(self.cuttlefish) == 0

        self.controller.dispatch(
            'RAISE_TO',
            amt=200,
            player_id=self.pirate_player.id,
        )
        self.controller.dispatch(
            'RAISE_TO',
            amt=self.cuttlefish_player.stack,
            player_id=self.cuttlefish_player.id,
        )
        self.controller.dispatch('FOLD', player_id=self.ajfenix_player.id)
        self.controller.dispatch('FOLD', player_id=self.cowpig_player.id)
        self.controller.dispatch('FOLD', player_id=self.pirate_player.id)

        expected_bonuses = sum(200 * bb for bb in CASH_GAME_BBS[1:3])

        user_bal = self.cuttlefish.userbalance().balance
        cashier_bal = balance(self.cuttlefish)
        earned_bal = earned_chips(self.cuttlefish)

        #user_bal == cashier_bal == earned_bal == expected_bonuses
        # TODO This test is failing
        assert user_bal == cashier_bal == earned_bal == expected_bonuses


class PrivateGamesDontLevelUpTest(GenericTableTest):
    def test_private_games_dont_levelup(self):
        self.table.is_private = True
        self.table.save()

        next_level_chips = Decimal(CASH_GAME_BBS[1] * N_BB_TO_NEXT_LEVEL / 2)
        self.pirate_player.stack = next_level_chips
        self.cuttlefish_player.stack = next_level_chips
        self.controller.subscribers = [
            LevelSubscriber(self.accessor),
            BankerSubscriber(self.accessor),
        ]

        self.setup_hand(
            blinds_positions={
                'btn_pos': 1,
                'sb_pos': 2,
                'bb_pos': 3,
            },
            player_hole_cards={
                self.pirate_player: '2s,3s',
                self.cuttlefish_player: 'Qh,Ac',
                self.ajfenix_player: '2c,8d',
                self.cowpig_player: '3d,Th'
            },
            board_str='As,Ad,Qd,6s,7s',
        )

        assert self.cuttlefish.cashtables_level == CASH_GAME_BBS[0]
        assert self.cuttlefish.tournaments_level == TOURNEY_BUYIN_AMTS[0]

        self.controller.dispatch(
            'RAISE_TO',
            player_id=self.pirate_player.id,
            amt=self.pirate_player.stack
        )
        self.controller.dispatch('CALL', player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD', player_id=self.ajfenix_player.id)
        self.controller.dispatch('FOLD', player_id=self.cowpig_player.id)

        assert self.pirate.cashtables_level == CASH_GAME_BBS[0]
        assert self.pirate.tournaments_level == TOURNEY_BUYIN_AMTS[0]

        self.cuttlefish.userstats().refresh_from_db()
        del self.cuttlefish.games_level # delete cached property
        assert self.cuttlefish.cashtables_level == CASH_GAME_BBS[0]


class UserStatsSubscriberTest(GenericTableTest):
    def test_hands_played(self):
        """Test if each hand is correctly counted"""
        self.user_stats_sub = UserStatsSubscriber(self.accessor)
        self.controller.subscribers.append(self.user_stats_sub)
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2

        self.controller.step()
        self.controller.commit()

        for _ in range(30):
            self.controller.dispatch(
                'FOLD',
                player_id=self.accessor.next_to_act().id
            )
        for player in self.accessor.active_players():
            player.user.userstats().refresh_from_db()
            # In 30 folds for a 4 players table we will have 10 hands played
            assert player.user.userstats().hands_played == 10
