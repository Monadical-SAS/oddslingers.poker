import os
import random
import traceback
import statistics
import datetime

from time import time
from os import remove

from django.test import tag
from django.conf import settings

from oddslingers.utils import DoesNothing, to_json_str, TempRandomSeed
from oddslingers.mutations import execute_mutations

from poker.bots import get_robot_move
from poker.cards import Card
from poker.constants import (NL_HOLDEM, PL_OMAHA, NL_BOUNTY, Event,
                             PlayingState)
from poker.controllers import (HoldemController, OmahaController,
                                BountyController, controller_type_for_table)
from poker.handhistory import DBLog
from poker.megaphone import gamestate_json
from poker.models import Player, PokerTable, HandHistory
from poker.subscribers import TableStatsSubscriber, LogSubscriber
from poker.game_utils import fuzzy_get_game
from poker.replayer import ActionReplayer
from poker.subscribers import Subscriber

from rewards.subscribers import BadgeSubscriber  # noqa
from rewards.tests import FivePlayerBadgeTest

from banker.mutations import buy_chips

class BotTest(FivePlayerBadgeTest):
    def setUp(self):
        super().setUp()
        for player in self.players:
            positions = list(range(5))
            random.shuffle(positions)

            for player, pos in zip(self.players, positions):
                player.position = pos
                player.save()
        stats_subscriber = TableStatsSubscriber(self.controller.accessor)
        self.controller.subscribers.append(stats_subscriber)
        self.dump_filename = os.path.join(settings.DEBUG_DUMP_DIR, 'filedump_test.json')

    def tearDown(self):
        super().tearDown()
        try:
            remove(self.dump_filename)
        except FileNotFoundError:
            pass

    def simulate_hand_and_test_assumptions(self, controller, stupid_ai):
        acc = controller.accessor
        curr_hand = acc.table.hand_number

        for player in acc.players:
            if not player.seated and player.stack >= acc.table.min_buyin:
                # print('joining table:', player)
                controller.join_table(player.user.id)

        for player in acc.players:
            if (not player.playing_state == PlayingState.SIT_IN_PENDING
                    and player.is_sitting_out()
                    and player.stack >= acc.min_amt_to_play(player)):
                controller.dispatch('sit_in', player_id=player.id)

        assert acc.enough_players_to_play()

        acc.is_out_of_time = lambda player: True
        timeout_players = []
        back_in_players = []

        left_table = []

        while acc.table.hand_number == curr_hand:
            next_to_act = acc.next_to_act()
            # print('next_to_act:', next_to_act)
            if random.random() > 0.1:
                action, kwargs = get_robot_move(acc,
                                             controller.log,
                                             delay=False,
                                             stupid=stupid_ai,
                                             warnings=False)
                # print(player, action, kwargs)
                controller.dispatch(action, **kwargs)

                if (action.lower() == 'fold'
                        and random.random() > 0.8
                        and acc.table.hand_number == curr_hand):
                    # print('leaving seat...')
                    # 20% of the time, player decides to get up after folding
                    controller.dispatch('leave_seat', player_id=next_to_act.id)
                    left_table.append(next_to_act)

            else:
                # 5% of the time, simulate running out of time
                # print('timed_dispatch running')
                controller.timed_dispatch()
                if next_to_act.stack >= acc.min_amt_to_play(next_to_act):
                    timeout_players.append(next_to_act)

                    # sometimes, the player changes their mind
                    if random.random() > 0.3:
                        # print('jk coming back')
                        nvm = timeout_players.pop()
                        back_in_players.append(nvm)
                        controller.dispatch('sit_in', player_id=nvm.id)

            # try:
            self.assertEqual(1400, sum(p.stack + p.total_contributed()
                                                    for p in acc.players))
            self.assert_avg_stack_in_stats(controller)
            self.assert_no_private_data_leaks(controller)
            self.assert_blinds_invariants(controller)
            self.assert_card_number(controller)
            self.assert_inactive_players_have_no_in_hand_state(controller)
            self.assert_private_json_in_broadcast_to_sockets(controller)
            self.assert_consistent_pot_size(controller)
            self.assert_animation_invariants(controller)
            # 2% of the time test debug dumps -- too costly to do every time
            if random.random() < 0.02:
                self.assert_logging_replaying_works(controller)

            # except Exception as e:
            #     self.controller.log.save_to_file('test.json', notes=str(e))
            #     print(e)
            #     import ipdb; ipdb.set_trace()
            #     pass

        for player in timeout_players:
            assert player.is_sitting_out()

        for player in left_table:
            assert not player.seated

    def assert_avg_stack_in_stats(self, controller):
        acc = controller.accessor
        if len(acc.active_players()) == 5:
            assert acc.table.stats.avg_stack == 1400 / 5

    def assert_consistent_pot_size(self, controller):
        acc = controller.accessor
        sidepots = acc.sidepot_summary(exclude_uncollected_bets=True)
        sidepot_total = sum(pot for pot, _ in sidepots)
        uncollected = sum(p.uncollected_bets for p in acc.players)
        curr_pot = acc.current_pot()
        assert sidepot_total + uncollected == curr_pot, \
                'current_pot() should always be the money in the '\
                'center + money in front of the players.'

    def assert_no_private_data_leaks(self, controller):
        acc = controller.accessor
        subs = controller.subscribers

        def raise_on_private_leak(player_json):
            if not player_json:
                return

            if 'cards' in player_json:
                for card in player_json['cards'].values():
                    if card['card'] != '?':
                        raise Exception('Private data leak detected!')

            if 'available_actions' in player_json:
                raise Exception('Available_actions is leaking')

        for player in acc.seated_players():
            payload = gamestate_json(acc, player, subs)

            for player_id, player_json in payload['players'].items():
                if player_id != str(player.id):
                    raise_on_private_leak(player_json)

            for animation in payload['animations']:
                if 'diff' in animation and 'players' in animation['diff']:
                    for player_id, player_json in animation['diff']['players'].items():
                        if player_id != str(player.id):
                            raise_on_private_leak(player_json)

    def assert_animation_invariants(self, controller):
        acc = controller.accessor
        subs = controller.subscribers

        player = random.choice(acc.seated_players())
        payload = gamestate_json(acc, player, subs)

        for animation in payload['animations']:
            if animation['type'] == 'NEW_STREET':
                assert any(
                    'sidepot_summary' in patch['path']
                    for patch in animation['patches']
                ), 'NEW_STREET should always patch sidepot_summary'

                uncollected_paths = [
                    patch['path'][:patch['path'].index('/amt')]
                    for patch in animation['patches']
                    if 'uncollected_bets' in patch['path']
                ]

                assert len(uncollected_paths), \
                        'NEW_STREET should always patch uncollected_bets'

                for patch_path in uncollected_paths:
                    assert patch_path in animation['value'], \
                            'Frontend needs all uncollected_bets in [value]'

    def assert_blinds_invariants(self, controller):
        acc = controller.accessor
        if not acc.enough_players_to_play():
            return

        table = acc.table
        sb = table.sb_idx
        bb = table.bb_idx
        btn = table.btn_idx

        # assert the bb and btn are different
        assert btn != bb

        # assert nobody ever gets dealt cards between sb and bb
        n_seats_to_check = (bb - sb) % table.num_seats
        for pos in range(sb + 1, sb + n_seats_to_check):
            plyr = acc.players_at_position(pos, active_only=True)
            if plyr:
                assert not plyr.cards

    def assert_card_number(self, controller):
        acc = controller.accessor
        if acc.table.table_type == NL_HOLDEM:
            for plyr in acc.players:
                if plyr:
                    assert len(plyr.cards) == 0 or len(plyr.cards) == 2

        if acc.table.table_type == PL_OMAHA:
            for plyr in acc.players:
                if plyr:
                    assert len(plyr.cards) == 0 or len(plyr.cards) == 4

    def assert_inactive_players_have_no_in_hand_state(self, controller):
        for player in controller.accessor.players:
            if player.is_sitting_out() or not player.seated:
                player._assert_no_inhand_state()

    def assert_private_json_in_broadcast_to_sockets(self, controller):
        acc = controller.accessor
        subs = controller.subscribers
        for player in acc.active_players():
            json_to_send = gamestate_json(acc, player, subs)
            assert "players" in json_to_send
            assert 'cards' in json_to_send['players'][str(player.id)]

    def assert_logging_replaying_works(self, controller):
        # print('assert_logging_replaying_works()')
        controller.debug_filedump('this is a test', self.dump_filename)

        rep = ActionReplayer.from_file(self.dump_filename)
        hand_idx = random.choice(range(len(rep.hands)))
        rep.skip_to_hand_idx(hand_idx)
        deck_str = rep.accessor.table.deck_str
        hand_number = rep.accessor.table.hand_number

        i = 0
        while True:
            try:
                rep.step_forward(multi_hand=True)
            except StopIteration:
                break

            if rep.accessor.table.hand_number != hand_number and deck_str:
                assert deck_str != rep.accessor.table.deck_str, \
                        'Two consecutive same deals == critical bug!\n'\
                        f'deck_str: {deck_str}\n'\
                        f'rep deck_str: {rep.accessor.table.deck_str}\n'\
                        f'hand_number: {hand_number}\n'\
                        f'rep hand_number: {rep.accessor.table.hand_number}'
                deck_str = rep.accessor.table.deck_str
                hand_number = rep.accessor.table.hand_number

            i += 1
            if i > 50000:
                raise Exception(
                    'Replayer stepped forward 50000 times. ',
                    f'Something is broken:\n{rep.describe(print_me=False)}'
                )


@tag('monte-carlo')
class HoldemBotTest(BotTest):
    def test_holdem_ai_moves(self):
        self.controller = HoldemController(self.table, self.players)
        # self.controller.verbose = True
        self.controller.step()
        self.controller.commit()
        self.accessor = self.controller.accessor
        acc = self.accessor

        while acc.enough_players_to_play() and acc.table.hand_number < 100:
            try:
                ctrl = fuzzy_get_game(self.controller.accessor.table.id)
                acc = ctrl.accessor
                self.simulate_hand_and_test_assumptions(ctrl, stupid_ai=False)
            except Exception as err:
                msg = to_json_str({
                    'state': acc.describe(False),
                    'err': traceback.format_exc(),
                })
                ctrl.dump_for_test(hand='all',
                                   fn_pattern='simfail_',
                                   notes=msg)
                raise type(err)(str(err)).with_traceback(err.__traceback__)


@tag('monte-carlo')
class BountyBotTest(BotTest):
    def test_holdem_ai_moves(self):
        self.table.table_type = NL_BOUNTY
        self.controller = BountyController(self.table, self.players)
        # self.controller.verbose = True
        self.controller.step()
        self.controller.commit()
        self.accessor = self.controller.accessor
        acc = self.accessor

        while acc.enough_players_to_play() and acc.table.hand_number < 100:
            try:
                ctrl = fuzzy_get_game(self.controller.accessor.table.id)
                acc = ctrl.accessor
                self.simulate_hand_and_test_assumptions(ctrl, stupid_ai=False)
            except Exception as err:
                msg = to_json_str({
                    'state': acc.describe(False),
                    'err': traceback.format_exc(),
                })
                ctrl.dump_for_test(hand='all',
                                   fn_pattern='simfail_',
                                   notes=msg)
                raise type(err)(str(err)).with_traceback(err.__traceback__)


class OmahaBotTest(BotTest):
    def test_omaha_ai_moves(self):
        self.table.table_type = PL_OMAHA
        self.controller = OmahaController(self.table, self.players)
        # self.controller.verbose = True
        self.controller.step()
        self.controller.commit()
        self.accessor = self.controller.accessor
        acc = self.accessor

        while acc.enough_players_to_play() and acc.table.hand_number < 100:
            try:
                ctrl = fuzzy_get_game(self.controller.accessor.table.id)
                acc = ctrl.accessor
                self.simulate_hand_and_test_assumptions(ctrl, stupid_ai=True)
            except Exception as err:
                msg = to_json_str({
                    'state': acc.describe(False),
                    'err': traceback.format_exc(),
                })
                ctrl.dump_for_test(hand='all',
                                   fn_pattern='simfail_',
                                   notes=msg)
                raise type(err)(str(err)).with_traceback(err.__traceback__)


class HHLogAssumptionsTest(BotTest):
    def hhlog_assumptions(self, controllertype):
        self.controller = controllertype(self.accessor.table,
                                         log=DBLog(self.accessor))
        self.accessor = self.controller.accessor
        self.controller.verbose = False

        class AssumptionTestSubscriber(Subscriber):
            def __init__(self, accessor):
                self.accessor = accessor
                self.last_hand_number = None

            def assert_new_hand(self):
                if not self.last_hand_number:
                    pass
                else:
                    assert self.last_hand_number != self.accessor.table.hand_number

            def commit(self):
                pass

            def updates_for_broadcast(self, player=None, spectator=None):
                return {}

            def dispatch(self, subj, event, **kwargs):
                if event == Event.END_HAND and isinstance(subj, PokerTable):
                    self.assert_new_hand()
                self.last_hand_number = self.accessor.table.hand_number

        self.controller.subscribers.append(
            AssumptionTestSubscriber(self.accessor)
        )
        self.controller.step()
        i = 0
        while i < 50 and self.accessor.enough_players_to_play():
            try:
                action, kwargs = get_robot_move(self.accessor,
                                             self.controller.log,
                                             delay=False,
                                             stupid=True,
                                             warnings=False)
                self.controller.dispatch(action, **kwargs)
                i += 1
            except Exception as err:
                self.controller.dump_for_test(hand='all',
                                              fn_pattern='hhlogfail_',
                                              notes=traceback.format_exc())
                raise type(err)(str(err)).with_traceback(err.__traceback__)


class HHLogAssumptionsHoldemTest(HHLogAssumptionsTest):
    def test_hhlog_assumptions_for_all_gametypes(self):
        self.table.table_type = NL_HOLDEM
        controllertype = controller_type_for_table(self.table)
        self.hhlog_assumptions(controllertype)


class HHLogAssumptionsBountyTest(HHLogAssumptionsTest):
    def test_hhlog_assumptions_for_all_gametypes(self):
        self.table.table_type = NL_BOUNTY
        controllertype = controller_type_for_table(self.table)
        self.hhlog_assumptions(controllertype)


class HHLogAssumptionsOmahaTest(HHLogAssumptionsTest):
    def test_hhlog_assumptions_for_all_gametypes(self):
        self.table.table_type = PL_OMAHA
        controllertype = controller_type_for_table(self.table)
        self.hhlog_assumptions(controllertype)


class OmahaHandTest(FivePlayerBadgeTest):
    def test_omaha(self):
        # in order:
        ajfenix = self.ajfenix_player.id  # (sb) $200
        cowpig = self.cowpig_player.id  # (bb) $100
        alexeimartov = self.alexeimartov_player.id  # $400
        pirate = self.pirate_player.id  # $400
        cuttlefish = self.cuttlefish_player.id  # $300

        self.table.table_type = PL_OMAHA

        self.controller = OmahaController(self.table,
                                          self.players,
                                          log=DoesNothing(),
                                          subscribers=[])
        self.controller.timing_events = lambda _, __: []

        dispatch = self.controller.player_dispatch

        self.controller.setup_hand()

        assert len(self.players[0].cards) == 4

        dispatch('raise_to', player_id=alexeimartov, amt=7)
        dispatch('fold', player_id=pirate)
        dispatch('call', player_id=cuttlefish, amt=7)
        dispatch('fold', player_id=ajfenix)

        # $1 raise is too small
        with self.assertRaises(ValueError):
            dispatch('raise_to', player_id=cowpig, amt=1)

        # cannot bet, only raise
        with self.assertRaises(ValueError):
            dispatch('bet', player_id=cowpig, amt=2)

        # maximum bet should be $29
        with self.assertRaises(ValueError):
            dispatch('raise_to', player_id=cowpig, amt=30)

        dispatch('raise_to', player_id=cowpig, amt=29)

        dispatch('call', player_id=alexeimartov, amt=29)
        dispatch('call', player_id=cuttlefish, amt=29)

        assert self.controller.accessor.current_pot() == 29*3 + 1

        # FLOP
        self.controller.step()

        dispatch('bet', player_id=cowpig, amt=45)

        # not cowpig's turn to act
        with self.assertRaises(ValueError):
            dispatch('fold', player_id=cowpig)

        dispatch('call', player_id=alexeimartov)
        dispatch('fold', player_id=cuttlefish)

        assert self.controller.accessor.current_pot() == 88 + 90

        # TURN
        self.controller.step()

        # cowpig's remaining stack is (100 - 29 - 45 = 26)
        with self.assertRaises(ValueError):
            dispatch('bet', player_id=cowpig, amt=99)

        dispatch('bet', player_id=cowpig, amt=26)
        dispatch('call', player_id=alexeimartov, amt=26)

        self.cowpig_player.cards = [
            Card('Ah'), Card('Kc'), Card('Jh'), Card('Tc')
        ]
        self.alexeimartov_player.cards = [
            Card('8s'), Card('9c'), Card('8c'), Card('Ts')
        ]

        self.table.board = [Card('3c'), Card('Ac'), Card('2h'), Card('Jc')]

        self.controller.step()

        # cowpig should win, with the K-high flush
        assert self.alexeimartov_player.stack_available == 300
        assert self.cowpig_player.stack_available == 230

class BountyHandTest(FivePlayerBadgeTest):
    def test_bounty_payout(self):
        # in order:
        ajfenix = self.ajfenix_player.id  # (sb) $200
        cowpig = self.cowpig_player.id  # (bb) $100
        alexeimartov = self.alexeimartov_player.id  # $400
        pirate = self.pirate_player.id  # $400
        cuttlefish = self.cuttlefish_player.id  # $300

        def rigged_table_deal(self, card):
            rig = [Card('Js'), Card('2h'), Card('3s'), Card('9d'), Card('2c')]
            self.board = rig[:len(self.board) + 1]
            return (('board', self.board), *self.on_record_action())

        self.real_table_deal = PokerTable.on_deal # used in tearDown
        PokerTable.on_deal = rigged_table_deal

        cards_to_deal = {
            'ajfenix': [Card('8h'), Card('3h')],
            'cowpig': [Card('7s'), Card('2c')],
            'alexeimartov': [Card('Ad'), Card('3d')],
            'pirate': [Card('5h'), Card('7h')],
            'cuttlefish': [Card('9h'), Card('Ts')]
        }
        def rigged_player_deal(self, card):
            rig = cards_to_deal[self.username]
            self.cards = rig[:len(self.cards) + 1]
            return (('cards', self.cards),)

        self.real_player_deal = Player.on_deal  # used in tearDown
        Player.on_deal = rigged_player_deal

        self.table.table_type = NL_BOUNTY
        self.controller = BountyController(
            self.table, self.players,
            subscribers=[]) # rigged deal breaks AnimationSubscriber
        self.controller.subscribers = [
            LogSubscriber(self.controller.log),
            BadgeSubscriber(self.controller.accessor, self.controller.log)
        ]
        self.controller.step()

        # just making sure the monkeypatch worked
        assert self.ajfenix_player.cards == [Card('8h'), Card('3h')]

        dispatch = self.controller.dispatch
        dispatch('call', player_id=alexeimartov)
        dispatch('call', player_id=pirate)
        dispatch('call', player_id=cuttlefish)
        dispatch('call', player_id=ajfenix)
        dispatch('check', player_id=cowpig)

        dispatch('fold', player_id=ajfenix)
        dispatch('check', player_id=cowpig)
        dispatch('fold', player_id=alexeimartov)
        dispatch('fold', player_id=pirate)
        dispatch('fold', player_id=cuttlefish)

        # cowpig wins (typical)
        assert self.cowpig_player.stack == 108

        # board needs to be cleared for the bounty deal
        assert len(self.controller.accessor.table.board) == 0

        # and we enter a forced flip where cowpig gets dealt 27o again
        dispatch('fold', player_id=cowpig)

        # cuttlefish wins the flip
        assert self.cuttlefish_player.stack_available == 298 + 108 * 3

        # alexeimartov wins the sidepot
        assert self.alexeimartov_player.stack_available == 398 - 108
        assert self.ajfenix_player.stack_available == 198 - 108
        # pirate is never broke
        assert self.pirate_player.stack_available == 398 - 108

        # next hand is no longer a bounty all-in
        assert not self.table.bounty_flag

    def tearDown(self):
        PokerTable.on_deal = self.real_table_deal
        Player.on_deal = self.real_player_deal
        super().tearDown()


class BotBenchmarkTest(FivePlayerBadgeTest):
    def test_bot_benchmark(self):
        self.controller.step()

        n_actions = 1000
        n_actions = 0

        if n_actions:
            start_time = time()
            ai_times = []

            for player in self.players:
                execute_mutations(
                    buy_chips(player.user, 10000000)
                )
            for player in self.players:
                player.auto_rebuy = 200

            with TempRandomSeed(0):
                for _ in range(n_actions):
                    player = self.controller.accessor.next_to_act()
                    ai_start = time()
                    action, kwargs = get_robot_move(self.controller.accessor,
                                                 self.controller.log,
                                                 warnings=False,
                                                 delay=False,
                                                 stupid=False)
                    ai_times.append(time() - ai_start)

                    self.controller.dispatch(action, **kwargs)
                    # self.controller.describe()

            end_time = time()
            diff = end_time - start_time
            aps = n_actions / diff
            mean_ai = statistics.mean(ai_times)
            std_ai = statistics.stdev(ai_times)

            print('Bot benchmark:')
            print(f'{n_actions} performed in {diff} seconds')
            print(f'{aps} actions per second')
            print(f'max: {max(ai_times)}, mean: {mean_ai}, std: {std_ai}')


class DebugDumpOrbitsTest(FivePlayerBadgeTest):
    # 0: pirate       (400)
    # 1: cuttlefish   (300)
    # 2: ajfenix      (200)
    # 3: cowpig       (100)
    # 4: alexeimartov (400)
    def setUp(self):
        super().setUp()
        self.file_name = 'orbits_dump_test.json'

    def test_orbits_leave_seat_dump(self):
        execute_mutations(
            buy_chips(self.pirate, amt=1000)
        )
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: '7c,2d',
            self.players[1]: 'Kh,Ac',
            self.players[2]: 'Kc,Ad',
            self.players[3]: 'Kd,Ah',
            self.players[4]: '7d,2h',
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)
        ctrl = self.controller
        acc = self.controller.accessor
        ctrl.dispatch('sit_out', player_id=self.cowpig_player.id)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)

        assert len(acc.active_players()) == 4

        hand_counter = 0
        # We need to skip cowpig 3 times
        while hand_counter < 20:
            ctrl.dispatch('fold', player_id=acc.next_to_act().id)
            ctrl.dispatch('fold', player_id=acc.next_to_act().id)
            ctrl.dispatch('fold', player_id=acc.next_to_act().id)
            hand_counter += 1

        ctrl.dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.dispatch('leave_seat', player_id=self.pirate_player.id)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)

        ctrl.join_table(self.pirate.id)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)
        self._simulate_test_replayer_dump_file()

    def _simulate_test_replayer_dump_file(self):
        self.controller.debug_filedump('this is a test', self.file_name)

        rep = ActionReplayer.from_file(self.file_name)
        # In hand 17 cowpig has 3 orbits and is sitting out

        rep.skip_to_hand_idx(16)

        i = 0
        while True:
            try:
                rep.step_forward(multi_hand=True)
            except StopIteration:
                break
            i += 1
            if i > 50000:
                raise Exception(
                    'Replayer stepped forward 50000 times. ',
                    f'Something is broken:\n{rep.describe(print_me=False)}'
                )

    def tearDown(self):
        super().tearDown()
        try:
            remove(self.file_name)
        except FileNotFoundError:
            pass


class DifferentDatesTimestampTest(FivePlayerBadgeTest):
    def test_timestamp_with_different_dates(self):
        # in order:
        ajfenix = self.ajfenix_player.id  # (sb) $200
        # cowpig = self.cowpig_player.id  # (bb) $100
        alexeimartov = self.alexeimartov_player.id  # $400
        pirate = self.pirate_player.id  # $400
        cuttlefish = self.cuttlefish_player.id  # $300

        table = self.controller.table

        self.controller.setup_hand()

        self.controller.dispatch('FOLD', player_id=alexeimartov)
        self.controller.dispatch('FOLD', player_id=pirate)
        self.controller.dispatch('FOLD', player_id=cuttlefish)
        # at this point table is paused 23 hours

        hand = HandHistory.objects.get(hand_number=table.hand_number)
        hand_ts = hand.timestamp
        for idx, action in enumerate(hand.actions()):
            action.timestamp = hand_ts - datetime.timedelta(hours=23) + datetime.timedelta(seconds=idx)
            action.save()
        hand.save()

        # we are simulating resuming the table after 23 hours, so timestamp
        # with just hours, minuts and seconds is lower than before
        self.controller.dispatch('FOLD', player_id=ajfenix)
