import json

from os import remove, path

from django.test import TestCase

from oddslingers.utils import ExtendedEncoder

from poker.controllers import HoldemController
from poker.handhistory import JSONLog, DBLog, MultiLog
from poker.models import HandHistory, HandHistoryEvent, HandHistoryAction
from poker.replayer import EventReplayer, ActionReplayer
from poker.tests.test_controller import GenericTableTest
from poker.subscribers import LogSubscriber
from poker.constants import HH_TEST_PATH


class JSONLogTest(GenericTableTest):
    def setUp(self):
        super().setUp()
        self.log = JSONLog(self.accessor)
        self.logsub = LogSubscriber(self.log)

        self.controller.log = self.log
        self.controller.subscribers = [self.logsub]

    def test_jsonlog(self):
        self.controller.setup_hand()
        self.log.save_to_file('JSONLogTest.tmp')

    def tearDown(self):
        super(JSONLogTest, self).tearDown()
        remove('JSONLogTest.tmp')


class DBLogTest(GenericTableTest):
    def setUp(self):
        super().setUp()
        self.log = DBLog(self.accessor)
        self.logsub = LogSubscriber(self.log)

        self.controller.log = self.log
        self.controller.subscribers = [self.logsub]
        self.controller.commit()

    def tearDown(self):
        super(DBLogTest, self).tearDown()
        HandHistoryEvent.objects.all().delete()
        HandHistoryAction.objects.all().delete()
        HandHistory.objects.all().delete()


class DBLogSetupHandTest(DBLogTest):
    def test_setup_hand(self):
        self.controller.setup_hand()
        self.controller.commit()
        self.log.save_to_file('DBLogSetupHandTest.tmp')

    def tearDown(self):
        super().tearDown()
        remove('DBLogSetupHandTest.tmp')


class DBLogFilterPrivateEventsTest(DBLogTest):
    def test_get_log_filtering(self):
        self.setup_hand()
        self.dispatch_random_actions(25)

        player = self.players[0]
        log = self.log.get_log(player=self.players[0])

        for hand in log['hands']:
            for event in hand['events']:
                if (event['event'] == 'DEAL'
                        and event['subj'] != player.username):
                    assert event['args']['card'] == '?'


class DBLogActionsTest(DBLogTest):
    def test_get_log(self):
        acc = self.controller.accessor
        ctrl = self.controller
        log = ctrl.log
        ctrl.step()
        ctrl.dispatch('raise_to', player_id=acc.next_to_act().id, amt=10)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)

        json_log = log.get_log()
        assert len(json_log['hands'][0]['actions']) == 3



class DBLogUnsavedObjectsTest(DBLogTest):
    def test_unsaved_objects_helper_function(self):
        ctrl = self.controller
        acc = ctrl.accessor
        ctrl.step()
        # preflop
        ctrl.player_dispatch(
            'raise_to', player_id=acc.next_to_act().id, amt=10
        )
        ctrl.player_dispatch(
            'call', player_id=acc.next_to_act().id
        )
        ctrl.player_dispatch(
            'call', player_id=acc.next_to_act().id
        )
        ctrl.player_dispatch(
            'fold', player_id=acc.next_to_act().id
        )
        ctrl.step()
        # flop
        ctrl.player_dispatch(
            'bet', player_id=acc.next_to_act().id, amt=10
        )
        ctrl.player_dispatch(
            'fold', player_id=acc.next_to_act().id
        )
        ctrl.player_dispatch(
            'fold', player_id=acc.next_to_act().id
        )
        ctrl.step()
        # next hand
        ctrl.player_dispatch(
            'call', player_id=acc.next_to_act().id
        )

        unsaved_hands = self.log._unsaved_hands()

        assert len(unsaved_hands) == 2
        assert len(unsaved_hands[0]['actions']) == 7
        assert len(unsaved_hands[1]['actions']) == 1


class MultiLogTest(GenericTableTest):
    def setUp(self):
        super().setUp()
        self.jsonlog = JSONLog(self.accessor)
        self.dblog = DBLog(self.accessor)
        self.log = MultiLog((self.jsonlog, self.dblog))
        self.logsub = LogSubscriber(self.log)

        self.controller.log = self.log
        self.controller.subscribers = [self.logsub]

    def assert_all_equal_except_timestamps(self, obj1, obj2):
        if isinstance(obj1, list):
            assert isinstance(obj2, list)
            for item1, item2 in zip(obj1, obj2):
                self.assert_all_equal_except_timestamps(item1, item2)
        elif isinstance(obj1, dict):
            assert isinstance(obj2, dict)

            for k in obj1.keys():
                if k != 'timestamp' and k != 'ts' and k != 'accessed':
                    assert k in obj2
                    self.assert_all_equal_except_timestamps(obj1[k], obj2[k])
        else:
            self.assertEqual(obj1, obj2)

    def diff_except_timestamps(self, obj1, obj2):
        # diff to go from obj1 to obj2. not necessarily reflexive.
        if isinstance(obj1, list):
            if not isinstance(obj2, list):
                return obj2
            return [
                self.diff_except_timestamps(item1, item2)
                for item1, item2 in zip(obj1, obj2)
            ]

        elif isinstance(obj1, dict):
            if not isinstance(obj2, dict):
                return obj2

            return {
                k: (self.diff_except_timestamps(obj1[k], obj2[k])
                    if k in obj2
                    else 'deleted')
                for k in obj1.keys()
                if k not in ('timestamp', 'ts', 'accessed')
            }

        elif obj1 != obj2:
            return obj2

        return 'n/a'

    def tearDown(self):
        super().tearDown()
        HandHistoryEvent.objects.all().delete()
        HandHistoryAction.objects.all().delete()
        HandHistory.objects.all().delete()


class UnsavedObjectsTest(MultiLogTest):
    def test_include_unsaved_objects(self):
        self.controller.step()
        # fold around twice without committing
        for _ in range(2 * (len(self.accessor.active_players()) - 1)):
            next_id = self.controller.accessor.next_to_act().id
            self.controller.player_dispatch('fold', player_id=next_id)
            self.controller.step()

        db_log = self.dblog.get_log()
        json_log = self.jsonlog.get_log()

        assert len(db_log['hands']) == 3,\
                'should be two folded-around hands plus the '\
                'new hand that just started'

        self.assert_all_equal_except_timestamps(db_log, json_log)

        unsaved_log = self.dblog._unsaved_hands()
        unsaved_log = ExtendedEncoder.convert_for_json(unsaved_log)
        unsaved_log = [
            self.dblog._convert_hand(unsaved_log[hn], None)
            for hn in sorted(unsaved_log.keys())
        ]

        # exp = json_log['hands']
        # obs = unsaved_log

        # import ipdb; ipdb.set_trace()
        self.assert_all_equal_except_timestamps(unsaved_log, json_log['hands'])


class LogBetweenSerializationTest(MultiLogTest):
    def test_log_between_serializations(self):
        self.controller.step()
        # fold around while committing
        for _ in range(len(self.accessor.active_players()) - 1):
            next_id = self.controller.accessor.next_to_act().id
            self.controller.dispatch('fold', player_id=next_id)

        # fold around without committing
        for _ in range(len(self.accessor.active_players()) - 1):
            next_id = self.controller.accessor.next_to_act().id
            self.controller.player_dispatch('fold', player_id=next_id)
            self.controller.step(end_hand_stop=True)

        db_log = self.dblog.get_log()
        json_log = self.jsonlog.get_log()
        self.assert_all_equal_except_timestamps(db_log, json_log)

        self.controller.end_hand()

        db_log = self.dblog.get_log()
        json_log = self.jsonlog.get_log()
        self.assert_all_equal_except_timestamps(db_log, json_log)

        self.controller.setup_hand()

        db_log = self.dblog.get_log()
        json_log = self.jsonlog.get_log()
        self.assert_all_equal_except_timestamps(db_log, json_log)


class EquivalentLogsTest(MultiLogTest):
    def test_dblog_and_json_log_are_equivalent(self):
        db_obj = self.dblog.get_log(player='all')
        json_obj = self.jsonlog.get_log(player='all')
        self.assert_all_equal_except_timestamps(db_obj, json_obj)
        self.assert_all_equal_except_timestamps(json_obj, db_obj)

        self.controller.step()
        self.controller.commit()

        db_obj = self.dblog.get_log(player='all')
        json_obj = self.jsonlog.get_log(player='all')
        self.assert_all_equal_except_timestamps(db_obj, json_obj)
        self.assert_all_equal_except_timestamps(json_obj, db_obj)

        self.controller.dispatch('FOLD',
                                 player_id=self.accessor.next_to_act().id)

        db_obj = self.dblog.get_log(player='all')
        json_obj = self.jsonlog.get_log(player='all')
        self.assert_all_equal_except_timestamps(db_obj, json_obj)
        self.assert_all_equal_except_timestamps(json_obj, db_obj)

        self.dblog.save_to_file('testfile_dblog.tmp')
        self.jsonlog.save_to_file('testfile_jsonlog.tmp')
        with open('testfile_dblog.tmp') as dblog_file:
            db_obj = json.load(dblog_file)

        with open('testfile_jsonlog.tmp') as jsonlog_file:
            json_obj = json.load(jsonlog_file)

        self.assert_all_equal_except_timestamps(db_obj, json_obj)
        self.assert_all_equal_except_timestamps(json_obj, db_obj)

        assert len(self.dblog.hands) == 1

    def tearDown(self):
        super().tearDown()
        remove('testfile_jsonlog.tmp')
        remove('testfile_dblog.tmp')


class ReplayerTest(GenericTableTest):
    def setUp(self):
        super().setUp()
        self.controller = HoldemController(self.table,
                                           self.players,
                                           DBLog(self.accessor))
        self.log = self.controller.log

    def tearDown(self):
        super(ReplayerTest, self).tearDown()
        HandHistoryEvent.objects.all().delete()
        HandHistoryAction.objects.all().delete()
        HandHistory.objects.all().delete()


class EventReplayerSetupTest(ReplayerTest):
    def test_replayer(self):
        self.setup_hand()
        self.dispatch_random_actions(9)

        log = self.controller.log.get_log(player='all')
        replayer = EventReplayer(log)

        while True:
            try:
                replayer.step_forward()
            except StopIteration:
                break

        assert_equivalent_game_states(self.controller.accessor,
                                      replayer.controller.accessor)


class EventReplayerFromHHFileTest(ReplayerTest):
    def test_replayer(self):
        self.setup_hand()
        self.dispatch_random_actions(9)

        self.filename = "temp.json"
        self.controller.log.save_to_file(self.filename, player='all')
        with open(self.filename, 'r') as f:
            hh = json.load(f)

        replayer = EventReplayer(hh)

        while True:
            try:
                replayer.step_forward()
            except StopIteration:
                break

        assert_equivalent_game_states(self.controller.accessor,
                                      replayer.controller.accessor)

    def tearDown(self):
        super().tearDown()
        remove(self.filename)


class ActionReplayerTest(ReplayerTest):
    def test_action_replayer(self):
        self.controller.step()
        # add a few actions
        for _ in range(2 * (len(self.accessor.active_players()) - 1) + 1):
            next_id = self.controller.accessor.next_to_act().id
            self.controller.player_dispatch('fold', player_id=next_id)
            self.controller.step()

        log = self.controller.log.get_log(player='all')
        assert len(log['hands']) == 3
        replayer = ActionReplayer(log)
        while True:
            try:
                replayer.step_forward()
            except StopIteration:
                break

        assert_equivalent_game_states(self.controller.accessor,
                                      replayer.controller.accessor)


class CurrentHandLogTest(DBLogTest):
    def test_current_hand_log(self):
        self.controller.step()
        for _ in range(3):
            for _ in range(len(self.accessor.active_players()) - 1):
                next_id = self.controller.accessor.next_to_act().id
                self.controller.dispatch('fold', player_id=next_id)

        next_id = self.controller.accessor.next_to_act().id
        self.controller.dispatch('raise_to', player_id=next_id, amt=7)

        next_id = self.controller.accessor.next_to_act().id
        self.controller.dispatch('raise_to', player_id=next_id, amt=15)

        next_id = self.controller.accessor.next_to_act().id
        self.controller.player_dispatch('raise_to', player_id=next_id, amt=30)

        log = self.controller.log.current_hand_log()

        assert len(log['hands']) == 1
        assert log['hands'][0]['table']['hand_number'] == 3
        assert len(log['hands'][0]['actions']) == 3


class FrontendHandHistoryTest(TestCase):
    def test_frontend_handhistory(self):
        jsonlog = JSONLog(accessor=None) # we're not really using this
        with open(path.join(HH_TEST_PATH, 'a_few_hands.json')) as f:
            jsonlog.hands = json.load(f)['hands']

        frontend_log = jsonlog.frontend_log(None, 0, 1000)

        assert len(frontend_log) == len(jsonlog.hands)

        for hand in frontend_log:
            assert isinstance(hand['summary'], dict)
            assert isinstance(hand['summary']['title'], str)
            assert isinstance(hand['summary']['table_info'], str)
            assert isinstance(hand['summary']['history'], list)

class DBLogFrontendHandHistoryTest(DBLogTest):
    def test_frontend_handhistory_in_dblog(self):
        ctrl = self.controller
        acc = ctrl.accessor
        log = ctrl.log
        ctrl.step()
        ctrl.dispatch('raise_to', player_id=acc.next_to_act().id, amt=10)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)

        frontend_log = log.frontend_log(None, 0, 1000)
        assert len(frontend_log) == 1


def assert_equivalent_game_states(accessor1, accessor2):
    TABLE_FIELDS_TO_COMPARE = (
        'id', 'table_type', 'ante', 'min_buyin', 'max_buyin',
        'num_seats', 'sb', 'bb', 'btn_idx', 'sb_idx', 'bb_idx',
        'deck_str', 'board_str', 'precision', 'hand_number')
    table1 = accessor1.table.attrs(*TABLE_FIELDS_TO_COMPARE)
    table2 = accessor2.table.attrs(*TABLE_FIELDS_TO_COMPARE)
    table1_id = table1.pop('id')
    table2_id = table2.pop('id')

    for key in table1:
        assert table1[key] == table2[key]
    for key in table2:
        assert table1[key] == table2[key]

    # import ipdb; ipdb.set_trace()

    PLAYER_FIELDS_TO_COMPARE = (
        'table_id', 'stack', 'wagers', 'uncollected_bets',
        'pending_rebuy', 'position', 'seated', 'playing_state',
        'sit_out_at_blinds', 'owes_sb',
        'owes_bb', 'cards_str', 'last_action_int'
    )

    players1 = [
        player.attrs(*PLAYER_FIELDS_TO_COMPARE)
        for player in accessor1.seated_players()
    ]
    players2 = [
        player.attrs(*PLAYER_FIELDS_TO_COMPARE)
        for player in accessor2.seated_players()
    ]
    for player in players1:
        assert player.pop('table_id') == table1_id
    for player in players2:
        assert player.pop('table_id') == table2_id

    for player1, player2 in zip(players1, players2):
        for key in player1:
            assert player1[key] == player2[key]
        for key in player2:
            assert player1[key] == player2[key]


class DescribeFunctionsTest(DBLogTest):
    def test_describe_functions(self):
        self.setup_hand()
        self.dispatch_random_actions(25)

        # this just tests that the functions don't throw for now;
        #   you can set print_met=True to tweak
        # print('> DESCRIBE')
        describe = self.log.describe(print_me=False)  # noqa
        # print('\n> CURRENT HAND\n')
        curr_hand = self.log.describe(current_hand=True, print_me=False)  # noqa
        # print('\n> CURRENT HAND UNFILTERED\n')
        curr_hand = self.log.describe(  # noqa
            current_hand=True,
            filtered=False,
            for_player='all',
            print_me=False
        )
        # print('\n> FULL LOG, UNFILTERED EVENTS\n')
        full_log = self.log.describe(  # noqa
            filtered=False,
            print_me=False,
        )
        # print('\n> FULL LOG, UNFILTERED EVENTS, UNFILTERED CARDS\n')
        full_log_no_filt = self.log.describe(  # noqa
            for_player='all',
            filtered=False,
            print_me=False,
        )
