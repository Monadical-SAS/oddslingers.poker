import random

from decimal import Decimal

from django.contrib.auth import get_user_model

from banker.mutations import buy_chips
from banker.models import BalanceTransfer

from poker.tests.test_controller import GenericTableTest, FivePlayerTableTest
from poker.constants import Event, PlayingState
from poker.accessors import PokerAccessor
from poker.megaphone import gamestate_json

from oddslingers.mutations import execute_mutations


class ActivePlayersTest(GenericTableTest):
    def test_active_players_ordered(self):
        # need small and big blind index to be set to get first to act index
        self.table.sb_idx = 0
        self.table.bb_idx = 1
        self.table.save()
        player_list = self.accessor.active_players()
        self.assertEqual(
            ['pirate', 'cuttlefish', 'ajfenix', 'cowpig'],
            [p.username for p in player_list])


class IsPredealTest(GenericTableTest):
    def test_is_predeal_with_one_player(self):
        acc = self.controller.accessor
        cont = self.controller
        assert acc.is_predeal()

        cont.internal_dispatch(
            [(self.pirate_player, Event.LEAVE_SEAT, {'immediate': True})])
        cont.internal_dispatch(
            [(self.cowpig_player, Event.LEAVE_SEAT, {'immediate': True})])
        cont.internal_dispatch(
            [(self.ajfenix_player, Event.LEAVE_SEAT, {'immediate': True})])

        assert acc.is_predeal()
        cont.step()
        assert acc.is_predeal()
        cont.player_dispatch('SIT_OUT', player_id=self.cuttlefish_player.id)
        assert acc.is_predeal()
        cont.step()
        assert acc.is_predeal()


class MinRaiseAmt1Test(GenericTableTest):
    def test_min_raise_amt(self):
        pirate = self.accessor.player_by_username('pirate')

        pirate.dispatch('bet', amt=10)

        self.assertEqual(20, self.accessor.min_bet_amt())


class MinRaiseAmt2Test(GenericTableTest):
    def test_min_raise_amt(self):
        pirate = self.accessor.player_by_username('pirate')
        cuttlefish = self.accessor.player_by_username('cuttlefish')

        pirate.dispatch('bet', amt=10)
        cuttlefish.dispatch('raise_to', amt=20)

        self.assertEqual(30, self.accessor.min_bet_amt())


class MinRaiseAmt3Test(GenericTableTest):
    def test_min_raise_amt(self):
        pirate = self.accessor.player_by_username('pirate')
        cuttlefish = self.accessor.player_by_username('cuttlefish')
        ajfenix = self.accessor.player_by_username('ajfenix')

        pirate.dispatch('bet', amt=10)
        cuttlefish.dispatch('raise_to', amt=20)
        ajfenix.dispatch('raise_to', amt=35)

        self.assertEqual(50, self.accessor.min_bet_amt())


class MinRaiseAmt4Test(GenericTableTest):
    def test_min_raise_amt(self):
        pirate = self.accessor.player_by_username('pirate')
        cuttlefish = self.accessor.player_by_username('cuttlefish')
        ajfenix = self.accessor.player_by_username('ajfenix')
        cowpig = self.accessor.player_by_username('cowpig')

        pirate.dispatch('bet', amt=10)
        cuttlefish.dispatch('raise_to', amt=20)
        ajfenix.dispatch('raise_to', amt=35)
        cowpig.dispatch('fold')

        pirate.dispatch('call', amt=35)
        cuttlefish.dispatch('call', amt=35)

        pirate.dispatch('new_street')
        cuttlefish.dispatch('new_street')
        ajfenix.dispatch('new_street')
        self.assertEqual(2, self.accessor.min_bet_amt())

        pirate.dispatch('bet', amt=20)
        self.assertEqual(40, self.accessor.min_bet_amt())

        cuttlefish.dispatch('call', amt=20)
        self.assertEqual(40, self.accessor.min_bet_amt())

        ajfenix.dispatch('raise_to', amt=57)
        self.assertEqual(94, self.accessor.min_bet_amt())


class AtPositionTest(GenericTableTest):
    def test_players_at_position(self):
        cowpig = self.accessor.players_at_position(3)
        self.assertEqual('cowpig', cowpig.username)
        at_3 = self.accessor.players_at_position(3, active_only=True)
        self.assertEqual('cowpig', at_3.username)
        not_there = self.accessor.players_at_position(5, active_only=True)
        self.assertTrue(not_there is None)

        cowpig.playing_state = PlayingState.SITTING_OUT
        at_3 = self.accessor.players_at_position(3)
        self.assertTrue('cowpig', at_3.username)
        not_there = self.accessor.players_at_position(3, active_only=True)
        self.assertTrue(not_there is None)
        at_pos_3 = self.accessor.players_at_position(3, include_unseated=True)
        self.assertEqual(len(at_pos_3), 1)
        self.assertEqual(at_pos_3.pop().username, 'cowpig')

        cowpig.seated = False
        cowpig.playing_state = None
        not_there = self.accessor.players_at_position(3)
        self.assertTrue(not_there is None)
        not_there = self.accessor.players_at_position(3, active_only=True)
        self.assertTrue(not_there is None)
        at_pos_3 = self.accessor.players_at_position(3, include_unseated=True)
        self.assertEqual(len(at_pos_3), 1)
        self.assertEqual(at_pos_3.pop().username, 'cowpig')

        cowpig.position = 0
        cowpig.save()
        at_pos_0 = self.accessor.players_at_position(0, include_unseated=True)
        self.assertEqual(len(at_pos_0), 2)
        self.assertTrue('cowpig' in [p.username for p in at_pos_0])


class AvailableActionsTest(GenericTableTest):
    def setUp(self):
        self.new_user = get_user_model().objects.create_user(
            username='fslexcduck',
            email='vanessa@hello.com',
            password='banana'
        )
        execute_mutations(
            buy_chips(self.new_user, 10000)
        )
        super().setUp()

    def tearDown(self):
        BalanceTransfer.objects.all().delete()
        super().tearDown()

    def test_available_actions(self):
        controller = self.controller
        acc = self.accessor

        self.setup_hand(blinds_positions={
            'btn_pos': 3,
            'sb_pos': 0,
            'bb_pos': 1,
        })

        new_plyr = controller.join_table(user_id=self.new_user.id,
                                         buyin_amt=150)

        actions = acc.available_actions(new_plyr)
        expected_actions = {
            'BUY',
            'SET_AUTO_REBUY',
            'SIT_IN_AT_BLINDS',
            'SIT_IN',
            'LEAVE_SEAT',
        }
        self.assertEqual(expected_actions, {str(a) for a in actions})

        self.controller.dispatch('SIT_IN', player_id=new_plyr.id)
        actions = acc.available_actions(new_plyr)
        expected_actions = {
            'BUY',
            'SET_AUTO_REBUY',
            'SIT_IN_AT_BLINDS',
            'SIT_OUT',
            'LEAVE_SEAT',
        }
        self.assertEqual(expected_actions, {str(a) for a in actions})

        self.controller.dispatch('LEAVE_SEAT', player_id=new_plyr.id)
        assert new_plyr not in self.accessor.seated_players()


        actions = acc.available_actions(self.ajfenix_player.id)
        expected_actions = {
            'BUY',
            'SET_AUTO_REBUY',
            'SIT_OUT_AT_BLINDS',
            'FOLD',
            'CALL',
            'RAISE_TO',
            'SIT_OUT',
            'LEAVE_SEAT',
        }
        self.assertEqual(expected_actions, {str(a) for a in actions})

        # players who haven't acted yet
        sitting_in_acts = {
            'SET_AUTO_REBUY',
            'SIT_OUT_AT_BLINDS',
            'BUY',
            'SET_PRESET_CHECKFOLD',
            'SIT_OUT',
            'LEAVE_SEAT',
        }
        for p in [self.cuttlefish_player, self.cowpig_player]:
            if p.uncollected_bets == 2:
                acts = sitting_in_acts.union({'SET_PRESET_CHECK'})
            else:
                acts = sitting_in_acts.union({'SET_PRESET_CALL'})
            self.assertEqual(
                acts,
                {str(a) for a in acc.available_actions(p.id)}
            )

        # pirate already has more than the max buyin
        sitting_in_acts.remove('BUY')
        sitting_in_acts.add('SET_PRESET_CALL')
        self.assertEqual(
            sitting_in_acts,
            {str(a) for a in acc.available_actions(self.pirate_player.id)}
        )

        table_action = [
            *controller.call(player_id=self.ajfenix_player.id),
            *controller.fold(player_id=self.cowpig_player.id),
            *controller.call(player_id=self.pirate_player.id),
        ]
        controller.internal_dispatch(table_action)
        actions = acc.available_actions(self.cuttlefish_player.id)
        expected_actions = {
            'BUY',
            'SET_AUTO_REBUY',
            'SIT_OUT_AT_BLINDS',
            'FOLD',
            'CHECK',
            'RAISE_TO',
            'SIT_OUT',
            'LEAVE_SEAT',
        }
        self.assertEqual(expected_actions, {str(a) for a in actions})


class PublicPlayerJSONTest(GenericTableTest):
    def test_cards_hidden_in_public_json(self):
        self.controller.step()
        json = self.accessor.player_json(self.cowpig_player, private=False)
        for card in json['cards'].values():
            assert card['card'] == '?'


class AvailableActionsAfterAllInsTest(GenericTableTest):
    def test_available_actions(self):
        acc = self.accessor
        ctrl = self.controller
        self.ajfenix_player.position = 3
        self.cowpig_player.position = 2
        # 0: pirate_player          400
        # 1: cuttlefish_player      300
        # 2: cowpig_player          100
        # 3: ajfenix_player         200

        self.setup_hand(blinds_positions={
            'btn_pos': 3,
            'sb_pos': 0,
            'bb_pos': 1,
        })

        ctrl.dispatch('RAISE_TO',
                      player_id=self.cowpig_player.id,
                      amt=10)

        ctrl.dispatch('CALL',
                      player_id=self.ajfenix_player.id)

        ctrl.dispatch('FOLD',
                      player_id=self.pirate_player.id)

        ctrl.dispatch('RAISE_TO',
                      player_id=self.cuttlefish_player.id,
                      amt=75)

        ctrl.dispatch('RAISE_TO',
                      player_id=self.cowpig_player.id,
                      amt=100)

        ctrl.dispatch('RAISE_TO',
                      player_id=self.ajfenix_player.id,
                      amt=200)

        avail_act_strs = [
            str(act).lower()
            for act in acc.available_actions(self.cuttlefish_player)
        ]
        assert 'raise_to' not in avail_act_strs


class LoggedInPlayerTest(GenericTableTest):
    def test_current_pot(self):
        self.pirate_player.wagers = 100
        self.pirate_player.save()
        self.cuttlefish_player.wagers = 1000
        self.cuttlefish_player.save()

        self.assertEqual(1100, self.accessor.current_pot())


class FirstToActTest(GenericTableTest):
    def test_first_to_act_pos_before_deal(self):
        self.table.sb_idx = 0
        self.table.bb_idx = 1
        self.table.save()
        plyrs = [
            self.pirate_player,
            self.ajfenix_player,
            self.cuttlefish_player,
            self.cowpig_player
        ]
        # should be small blind idx if > 2 players at table
        accessor_more_than_two = PokerAccessor(self.table, plyrs)
        self.assertEqual(0, accessor_more_than_two.first_to_act_pos())
        # big blind index otherwise
        accessor_less_than_two = PokerAccessor(
            self.table,
            [self.pirate_player, self.ajfenix_player])
        self.assertEqual(1, accessor_less_than_two.first_to_act_pos())


class GetPlayerByUserIDTest(GenericTableTest):
    def test_player_by_user_id(self):
        acc = self.accessor
        cowpig_player = acc.player_by_user_id(self.cowpig_player.user.id)
        self.assertEqual(self.cowpig_player, cowpig_player)


class GetPlayerByNameTest(GenericTableTest):
    def test_player_by_username(self):
        acc = self.accessor
        cowpig_player = acc.player_by_username(self.cowpig_player.username)
        self.assertEqual(self.cowpig_player, cowpig_player)


class GetPlayerByUniqueIDTest(GenericTableTest):
    def test_player_by_player_id(self):
        acc = self.accessor
        cowpig_player = acc.player_by_player_id(self.cowpig_player.id)
        self.assertEqual(self.cowpig_player, cowpig_player)


class IsLegalBetsizeTest(GenericTableTest):
    def test_is_legal_betsize(self):
        acc = self.accessor
        assert not acc.is_legal_betsize(self.ajfenix_player, 500)
        assert acc.is_legal_betsize(self.ajfenix_player, 100)


class SidepotMembersTest(GenericTableTest):
    def test_sidepot_members_mid_hand(self):
        self.pirate_player.wagers = 100
        self.pirate_player.stack = 0
        self.pirate_player.save()
        self.cuttlefish_player.wagers = 1000
        self.cuttlefish_player.stack = 0
        self.cuttlefish_player.save()
        sidepot_members = self.accessor.sidepot_members(rotate=0)
        self.assertEqual(
            ['pirate'],
            [p.username for p in sidepot_members])


class SidepotMembersMidHandTest(GenericTableTest):
    def test_sidepot_members_just_main_pot(self):
        self.pirate_player.wagers = 100
        self.pirate_player.uncollected_bets = 0
        self.pirate_player.stack = 0
        self.pirate_player.last_action = Event['BET']
        self.pirate_player.save()

        self.cuttlefish_player.wagers = 200
        self.cuttlefish_player.uncollected_bets = 100
        self.cuttlefish_player.stack = 200
        self.cuttlefish_player.last_action = Event['BET']
        self.cuttlefish_player.save()

        self.ajfenix_player.wagers = 200
        self.ajfenix_player.uncollected_bets = 100
        self.ajfenix_player.stack = 0
        self.ajfenix_player.last_action = Event['CALL']
        self.ajfenix_player.save()

        self.cowpig_player.wagers = 400
        self.cowpig_player.uncollected_bets = 300
        self.cowpig_player.stack = 1000
        self.cowpig_player.last_action = Event['RAISE_TO']
        self.cowpig_player.save()

        sidepot_members = self.accessor.sidepot_members(
            rotate=0,
            exclude_uncollected_bets=True
        )
        self.assertEqual([], sidepot_members)

    def test_sidepot_members_one_side_pot(self):
        self.pirate_player.wagers = 100
        self.pirate_player.uncollected_bets = 0
        self.pirate_player.stack = 0
        self.pirate_player.last_action = Event['BET']
        self.pirate_player.save()

        self.cuttlefish_player.wagers = 300
        self.cuttlefish_player.uncollected_bets = 100
        self.cuttlefish_player.stack = 200
        self.cuttlefish_player.last_action = Event['BET']
        self.cuttlefish_player.save()

        self.ajfenix_player.wagers = 300
        self.ajfenix_player.uncollected_bets = 100
        self.ajfenix_player.stack = 0
        self.ajfenix_player.last_action = Event['CALL']
        self.ajfenix_player.save()

        self.cowpig_player.wagers = 500
        self.cowpig_player.uncollected_bets = 300
        self.cowpig_player.stack = 1000
        self.cowpig_player.last_action = Event['RAISE_TO']
        self.cowpig_player.save()

        sidepot_members = self.accessor.sidepot_members(
            rotate=0,
            exclude_uncollected_bets=True
        )
        self.assertEqual([self.pirate_player], sidepot_members)

class SidepotSummaryTest(GenericTableTest):
    def test_sidepot_summary(self):
        self.pirate_player.wagers = 100
        self.pirate_player.uncollected_bets = 0
        self.pirate_player.stack = 0
        self.pirate_player.last_action = Event['BET']
        self.pirate_player.save()

        self.cuttlefish_player.wagers = 300
        self.cuttlefish_player.uncollected_bets = 100
        self.cuttlefish_player.stack = 200
        self.cuttlefish_player.last_action = Event['BET']
        self.cuttlefish_player.save()

        self.ajfenix_player.wagers = 300
        self.ajfenix_player.uncollected_bets = 100
        self.ajfenix_player.stack = 0
        self.ajfenix_player.last_action = Event['CALL']
        self.ajfenix_player.save()

        self.cowpig_player.wagers = 500
        self.cowpig_player.uncollected_bets = 300
        self.cowpig_player.stack = 1000
        self.cowpig_player.last_action = Event['RAISE_TO']
        self.cowpig_player.save()

        sidepot_summary = self.accessor.sidepot_summary()
        self.assertEqual(sidepot_summary, [
            (
                Decimal(400),
                {
                    self.cuttlefish_player,
                    self.pirate_player,
                    self.cowpig_player,
                    self.ajfenix_player
                }
            ),
            (
                Decimal(600),
                {
                    self.cuttlefish_player,
                    self.cowpig_player,
                    self.ajfenix_player
                }
            ),
            (
                Decimal(200),
                {self.cowpig_player}
            )
        ])

        summary = self.accessor.sidepot_summary(exclude_uncollected_bets=True)
        self.assertEqual(summary, [
            (
                Decimal(400),
                {
                    self.cuttlefish_player,
                    self.pirate_player,
                    self.cowpig_player,
                    self.ajfenix_player
                }
            ),
            (
                Decimal(300),
                {
                    self.cuttlefish_player,
                    self.cowpig_player,
                    self.ajfenix_player
                }
            ),
        ])


class MinRaiseAmtPreflop1Test(FivePlayerTableTest):
    def test_min_raise_amt(self):
        self.controller.step()
        self.assertEqual(4, self.accessor.min_bet_amt())


class MinRaiseAmtPreflop2Test(FivePlayerTableTest):
    def test_min_raise_amt(self):
        self.controller.step()
        self.accessor.player_by_username('alexeimartov')\
                     .dispatch('raise_to', amt=5)

        self.assertEqual(8, self.accessor.min_bet_amt())


class MinRaiseAmtPreflop3Test(FivePlayerTableTest):
    def test_min_raise_amt(self):
        acc = self.controller.accessor
        self.controller.step()
        acc.player_by_username('alexeimartov').dispatch('raise_to', amt=5)
        acc.player_by_username('pirate').dispatch('raise_to', amt=10)
        acc.player_by_username('cuttlefish').dispatch('raise_to', amt=20)
        self.assertEqual(30, acc.min_bet_amt())


class MinRaiseAmtPreflop4Test(FivePlayerTableTest):
    def test_min_raise_amt(self):
        acc = self.controller.accessor
        self.controller.step()
        acc.player_by_username('alexeimartov').dispatch('call', amt=2)
        acc.player_by_username('pirate').dispatch('call', amt=2)
        acc.player_by_username('cuttlefish').dispatch('call', amt=2)
        acc.player_by_username('ajfenix').dispatch('call', amt=2)
        self.assertEqual(4, acc.min_bet_amt())


class MinAmtToPlayTest(FivePlayerTableTest):
    def test_min_amt_to_play(self):
        acc = self.controller.accessor

        # typically, player needs at least a big blind to play a hand
        assert acc.min_amt_to_play(self.ajfenix_player) == 2

        # if there's an ante, needs to be able to pay that too
        self.table.ante = 0.5
        assert acc.min_amt_to_play(self.ajfenix_player) == 2.5

        # if the player owes the sb, needs to be able to pay that too
        self.ajfenix_player.owes_sb = True
        assert acc.min_amt_to_play(self.ajfenix_player) == 3.5


class PlayersWhoCanPlayTest(FivePlayerTableTest):
    def test_players_who_can_play(self):
        for _ in range(100):
            for player in self.players:
                player.playing_state = PlayingState.SITTING_IN
                player.playing_state = PlayingState.SIT_IN_AT_BLINDS_PENDING

            sitting_out_player = random.choice(self.players)
            sitting_out_player.dispatch('sit_out')

            going_to_sit_in = random.choice(self.players)
            going_to_sit_in.dispatch('sit_out')
            going_to_sit_in.dispatch('sit_in_at_blinds', set_to=True)

            not_enough_to_play = random.choice(self.players)
            not_enough_to_play.dispatch('sit_out')
            going_to_sit_in.dispatch('sit_in_at_blinds', set_to=True)
            not_enough_to_play.stack = 0

            stand_up = random.choice(self.players)
            stand_up.dispatch('leave_seat')

            players = self.accessor.players_who_can_play()

            for p in players:
                playing = p.is_active()
                ready_to_play = (
                    p.playing_state == PlayingState.SIT_IN_AT_BLINDS_PENDING
                    and p.stack > self.accessor.min_amt_to_play(p)
                )
                self.assertTrue(playing or ready_to_play)


class GamestateJsonTest(GenericTableTest):
    def test_gamestate_jsons(self):
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2

        self.controller.step()
        self.controller.commit()

        subs = self.controller.subscribers
        acc = self.controller.accessor

        public_gamestate = gamestate_json(acc, None, subs)
        for pid, pdata in public_gamestate['players'].items():
            assert len(pdata['cards'])
            for card in pdata['cards'].values():
                assert card['card'] == '?'

        player_gamestate = gamestate_json(acc, self.cowpig_player, subs)
        for pid, pdata in player_gamestate['players'].items():
            for card in pdata['cards'].values():
                if pid == str(self.cowpig_player.id):
                    assert card['card'] != '?'
                else:
                    assert card['card'] == '?'

        # all_gamestate = gamestate_json(acc, 'all', subs)
        # for pid, pdata in all_gamestate['players'].items():
        #     for card in pdata['cards'].values():
        #         assert card != '?'


class NewPlayerWillActTest(GenericTableTest):
    def setUp(self):
        super().setUp()
        self.alexeimartov = get_user_model().objects.create_user(
            username='alexeimartov',
            email='marty@hello.com',
            password='banana'
        )
        execute_mutations(
            buy_chips(self.alexeimartov, 10000)
        )

    def test_new_player_will_act(self):
        self.controller.join_table(self.alexeimartov.id)

        alexeimartov = self.accessor.player_by_username('alexeimartov')
        self.controller.dispatch('SIT_IN', player_id=alexeimartov.id)

        self.controller.step()

        assert self.controller.accessor.will_act_this_round(alexeimartov)


class ActiveFirstToActPlayerTest(GenericTableTest):
    def test_active_first_to_act_player(self):
        '''
        with players in seats 0, 1, 2, 3
        and btn_idx == 1
        the first_to_act_pos preflop is 4, which has no active player.

        this asserts first_to_act() correctly returns the player at position 0
        '''

        self.table.btn_idx = 1
        self.controller.step()

        assert self.accessor.first_to_act_pos() == 4
        assert self.accessor.first_to_act() == self.pirate_player
