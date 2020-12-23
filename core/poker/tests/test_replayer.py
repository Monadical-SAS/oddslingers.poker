import json
import os

from django.test import TestCase

from oddslingers.settings import DEBUG_DUMP_DIR

from poker.constants import HH_TEST_PATH, PLAYER_REFRESH_FIELDS
from poker.replayer import EventReplayer, ActionReplayer
from poker.subscribers import AnimationSubscriber, InMemoryLogSubscriber
from poker.megaphone import gamestate_json
from poker.models import MockPokerTable, MockPlayer

from poker.tests.test_log import assert_equivalent_game_states, ReplayerTest


class MockModelsTest(TestCase):
    def test_mockplayer_has_mockpokertable(self):
        mock_table, _ = MockPokerTable.objects.update_or_create(
            name='my mock table',
            is_mock=True
        )
        mock_player, _ = MockPlayer.objects.update_or_create(
            mock_name='my mock player',
            table=mock_table
        )
        assert mock_table == mock_player.table
        mock_player.refresh_from_db(fields=PLAYER_REFRESH_FIELDS)
        assert mock_table == mock_player.table

class EventReplayerTest(TestCase):
    def setUp(self, filename='no_events.json', **kwargs):
        with open(filename, 'r') as f:
            self.hh = json.load(f)

        self.replayer = EventReplayer(self.hh, **kwargs)

    def tearDown(self):
        self.replayer.delete()


class ActionReplayerTest(TestCase):
    def setUp(self, filename='no_events.json', **kwargs):
        with open(filename, 'r') as f:
            self.hh = json.load(f)

        self.replayer = ActionReplayer(self.hh, **kwargs)

    def tearDown(self):
        self.replayer.delete()


class EndIterationTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'a_few_hands.json')
        super().setUp(self.filename)

    def test_step_forward_with_multihand(self):
        rep = self.replayer

        try:
            while True:
                rep.step_forward(multi_hand=True)
        except StopIteration:
            return

        assert False, "Should have hit a StopIteration"


class EventControlsTest(EventReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'a_few_hands.json')
        super().setUp(self.filename)

    def test_event_controls(self):
        self.replayer.skip_to_hand_idx(0)

        assert self.replayer.current_hand()['table']['hand_number'] == 0
        self.replayer.next_hand()
        assert self.replayer.current_hand()['table']['hand_number'] == 1
        self.replayer.next_hand()
        assert self.replayer.current_hand()['table']['hand_number'] == 2

        # 56 is a SIT_IN event; should be ignored
        self.replayer._skip_to_event(56)
        assert self.replayer.event_idx == 57

        self.replayer.step_forward()
        assert self.replayer.event_idx == 58

        self.replayer.step_back()
        # should step back over the SIT_IN event
        self.replayer.step_back()
        assert self.replayer.event_idx == 55

        self.replayer.step_forward()
        assert self.replayer.event_idx == 57

        with self.assertRaises(StopIteration):
            self.replayer._skip_to_event(944)


class IsLastHandTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'a_few_hands.json')
        super().setUp(self.filename)

    def test_consistent_potsize(self):
        self.replayer.skip_to_hand_number(8)
        assert self.replayer.is_last_hand()

        self.replayer.skip_to_hand_idx(-1)
        assert self.replayer.is_last_hand()

class ReplayerWithSubscribersTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'a_few_hands.json')
        super().setUp(self.filename, subscriber_types=[AnimationSubscriber])

    def test_animation_subscriber(self):
        self.replayer.skip_to_hand_idx(5)
        self.replayer.step_forward()
        subs = self.replayer.controller.subscribers

        gamestate = gamestate_json(self.replayer.accessor, subscribers=subs)

        assert 'animations' in gamestate

class ReplayerDescribeTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'a_few_hands.json')
        super().setUp(self.filename)

    def test_animation_subscriber(self):
        description = self.replayer.describe(print_me=False)
        # print(description)
        assert description


class ActionReplayerCurrentActionIsNextTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'a_few_hands.json')
        super().setUp(self.filename)

    def test_current_action_is_next(self):
        rep = self.replayer
        rep.subscriber_types = [InMemoryLogSubscriber]
        rep.skip_to_hand_idx(0)
        while True:
            try:
                rep.controller.subscribers[0].log = []
                next_action = rep.current_action()['action'].upper()
                rep.step_forward(multi_hand=True)
                rep.controller.subscribers[0].log
                former_action = str(rep.controller.subscribers[0].log[0][1])
                assert former_action == next_action
            except IndexError:
                break


class ActionReplayerMultiHandTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'a_few_hands.json')
        super().setUp(self.filename)

    def test_multi_hand_step_forward(self):
        self.replayer.skip_to_hand_idx(0)
        # self.replayer.verbose = True

        while True:
            try:
                self.replayer.step_forward(multi_hand=True)
            except StopIteration:
                break

        assert self.replayer.is_last_hand()


class EventReplayerCurrentEventIsNextTest(EventReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'a_few_hands.json')
        super().setUp(self.filename)

    def test_current_event_is_next(self):
        rep = self.replayer
        rep.subscriber_types = [InMemoryLogSubscriber]
        rep.skip_to_hand_idx(0)
        while True:
            try:
                rep.controller.subscribers[0].log = []
                next_event = rep.current_event()['event']
                rep.step_forward()
                rep.controller.subscribers[0].log
                former_event = str(rep.controller.subscribers[0].log[0][1])
                assert former_event == next_event
            except StopIteration:
                break


class TestReplayerConstruction(TestCase):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'a_few_hands.json')

    def test_from_file_on_action_replayer(self):
        with open(self.filename, 'r') as file:
            replayer = ActionReplayer.from_file(file, hand_idx=0, logging=True)

            assert replayer.current_action()["action"] == "FOLD", \
                "Did not set the first action correctly"

            replayer.step_forward()

            assert replayer.current_action()["action"] == "RAISE_TO", \
                "Did not set the first action correctly when moved forward"

            replayer.step_forward()
            replayer.step_forward()
            replayer.step_forward()

            axn_is_raise_to = replayer.current_action()["action"] == "RAISE_TO"
            subj_is_cowpig = replayer.current_action()["subj"] == "cowpig"
            assert (axn_is_raise_to and subj_is_cowpig), \
                "Did not set the action correctly when moved forward three " \
                "times"
            assert replayer.file == file, \
                "The returned replayer must to have the same file"
            assert replayer.hand_idx == 0, \
                "It's not setting the hand_idx as 0"
            assert replayer.action_idx == 4, \
                'Did not moved forward four actions'

    def test_from_file_on_event_replayer(self):
        with open(self.filename, 'r') as file:
            replayer = EventReplayer.from_file(file, hand_idx=1, logging=True)

            assert replayer.current_event()["event"] == "CHAT", \
                "Did set the first event correctly"

            replayer.step_forward()

            assert replayer.current_event()["event"] == "SET_BLIND_POS", \
                "Did not set the event correctly when moved forward"

            replayer.step_forward()
            replayer.step_forward()
            replayer.step_forward()

            assert replayer.current_event()["event"] == "POST", \
                "Did not set the event correctly when moved forward three " \
                "times"
            assert replayer.file == file, \
                "The returned replayer must to have the same file"
            assert replayer.hand_idx == 1, \
                "It's not setting the hand_idx as 1"

    def test_from_table_on_action_replayer(self):
        with open(self.filename, 'r') as file:
            initial_replayer = ActionReplayer(json_log=json.load(file),
                                              hand_idx=0,
                                              logging=True)
            initial_replayer.step_forward()
            initial_replayer.step_forward()
            initial_replayer.step_forward()
            initial_replayer.commit()

            replayer = ActionReplayer.from_table(
                initial_replayer.table,
                hand_idx=0,
                logging=True
            )

            replayer_curr_action = replayer.current_action()["action"].upper()
            initial_replyr_actions = initial_replayer.current_hand()["actions"]
            init_replyr_first_action = initial_replyr_actions[0]["action"]
            assert (replayer_curr_action == init_replyr_first_action), \
                "Did not set the first action correctly"

            replayer.step_forward()
            replayer.step_forward()

            replayer_curr_action = replayer.current_action()["action"].upper()
            init_replyr_third_action = initial_replyr_actions[2]["action"]
            assert (replayer_curr_action == init_replyr_third_action), \
                "Did not set the action correctly when moved forward 2 times"

            initial_replayer.skip_to_hand_idx(0)
            initial_replayer.step_forward()
            initial_replayer.step_forward()

            assert_equivalent_game_states(
                initial_replayer.accessor,
                replayer.accessor
            )

    def test_from_table_on_event_replayer(self):
        with open(self.filename, 'r') as file:
            initial_replayer = EventReplayer(
                json_log=json.load(file),
                hand_idx=0,
                logging=True
            )
            initial_replayer.step_forward()
            initial_replayer.step_forward()
            initial_replayer.step_forward()
            initial_replayer.commit()

            replayer = EventReplayer.from_table(
                initial_replayer.table,
                hand_idx=0,
                logging=True
            )

            replyr_curr_evnt_subj = replayer.current_event()["subj"]
            init_replyr_events = initial_replayer.current_hand()["events"]
            init_replyr_first_evnt = init_replyr_events[0]["subj"]
            assert (replyr_curr_evnt_subj == init_replyr_first_evnt), \
                "Did not set the first event correctly"

            replayer.step_forward()
            replayer.step_forward()

            replyr_curr_evnt_subj = replayer.current_event()["subj"]
            init_replyr_third_event = init_replyr_events[2]["subj"]
            assert (replyr_curr_evnt_subj == init_replyr_third_event), \
                "Did not set the first event correctly when moved forward"


class TestReplayerConstructorParams(TestCase):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'a_few_hands.json')

    def test_from_file_hand_number(self):
        rep = EventReplayer.from_file(self.filename, hand_idx=-2)
        assert rep.current_hand()['table']['hand_number'] == 7

        rep = ActionReplayer.from_file(
            self.filename, hand_idx=2, session_id='banana'
        )
        assert rep.current_hand()['table']['hand_number'] == 2
        assert rep.session_id == 'banana'

        rep = EventReplayer.from_file(
            self.filename, hand_number=2, session_id='banana', logging=True
        )
        assert rep.current_hand()['table']['hand_number'] == 2
        assert rep.logging
        assert rep.session_id == 'banana'

        rep = ActionReplayer.from_file(self.filename, hand_number=3)
        assert rep.current_hand()['table']['hand_number'] == 3
        assert rep.action_idx == 0

        rep = ActionReplayer.from_file(
            self.filename, hand_number=6, logging=True, session_id='banana'
        )
        assert rep.current_hand()['table']['hand_number'] == 6
        assert rep.logging
        assert rep.session_id == 'banana'


class ActionReplayerLoggingTest(TestCase):
    TEMP_FN = os.path.join(DEBUG_DUMP_DIR, 'tmp.json')
    def test_action_replayer_logging(self):
        with open('poker/tests/data/a_few_hands.json') as file:
            replayer = ActionReplayer.from_file(file,
                                                hand_idx=0,
                                                logging=True)

        while True:
            try:
                replayer.step_forward(multi_hand=True)
            except StopIteration:
                break

        replayer.controller.log.save_to_file(self.TEMP_FN, player='all')

        with open(self.TEMP_FN) as file:
            new_replayer = ActionReplayer.from_file(file, hand_idx=0)

        replayer.skip_to_hand_idx(0)

        while True:
            try:
                replayer.step_forward(multi_hand=True)
                new_replayer.step_forward(multi_hand=True)

                assert_equivalent_game_states(replayer.accessor,
                                              new_replayer.accessor)

            except StopIteration:
                break

    def tearDown(self):
        if os.path.isfile(self.TEMP_FN):
            os.remove(self.TEMP_FN)


class ReplayerOriginalLogTest(TestCase):
    TEMP_FN = os.path.join(DEBUG_DUMP_DIR, 'tmp.json')
    def test_original_log(self):
        with open('poker/tests/data/a_few_hands.json') as file:
            log_str = file.read()

        json_log = json.loads(log_str)
        replayer = ActionReplayer(json_log)
        assert json.dumps(json_log) == json.dumps(replayer.original_log())

        replayer.debug_filedump(self.TEMP_FN)
        with open(self.TEMP_FN) as f:
            assert json.dumps(json_log) == json.dumps(json.load(f))

    def tearDown(self):
        if os.path.isfile(self.TEMP_FN):
            os.remove(self.TEMP_FN)


class DescribeFunctionsTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'a_few_hands.json')
        super().setUp(self.filename)

    def test_describe_functions(self):
        rep = self.replayer
        rep.skip_to_hand_idx(3)
        # this just tests that the functions don't throw for now;
        #   you can set print_met=True to tweak

        # print('> DESCRIBE')
        describe = rep.describe(print_me=False)  # noqa
        # print('\n> FULL LOG\n')
        full_log = rep.describe_log(print_me=False)  # noqa
        # print('\n> FULL LOG UNFILTERED\n')
        full_log = rep.describe_log(filtered=False, print_me=False)  # noqa
        # print('\n> CURRENT HAND\n')
        current_hand = rep.describe_hand(print_me=False)  # noqa
        # print('\n> CURRENT HAND UNFILTERED\n')
        current_hand = rep.describe_hand(filtered=False, print_me=False)  # noqa


class PresetActionReplayTest(ReplayerTest):
    def test_preset_action_replay(self):
        self.setup_hand(blinds_positions={
            'btn_pos': 0,
            'sb_pos': 1,
            'bb_pos': 2
        })
        ctrl = self.controller
        ctrl.step()

        ctrl.dispatch(
            'SET_PRESET_CHECKFOLD',
            set_to='true',
            player_id=self.pirate_player.id
        )
        ctrl.dispatch('RAISE_TO', amt=8, player_id=self.cowpig_player.id)
        ctrl.dispatch('CALL', player_id=self.cuttlefish_player.id)

        log = self.controller.log.get_log(player='all')
        assert len(log['hands'][0]['actions']) == 4
        replayer = ActionReplayer(log)

        for _ in range(3):
            replayer.step_forward()

        assert str(self.pirate_player.last_action) == 'FOLD'
        assert str(self.cuttlefish_player.last_action) == 'CALL'


# class PortActionsTest(TestCase):
#     # rewrites the event streams in every hand history file to match the
#     #   actions, after some c
#     def test_not_really_a_test(self):
#         path = HH_TEST_PATH
#         hh_filenames = [
#             os.path.join(path, fn)
#             for fn in os.listdir(path)
#             if os.path.isfile(os.path.join(path, fn)) and '.json' in fn
#         ]

#         for fn in hh_filenames:
#             with open(fn) as file:
#                 if '"actions"' not in file.read():
#                     continue

#             with open(fn) as file:
#                 replayer = ActionReplayer.from_file(file,
#                                                     hand_idx=0,
#                                                     logging=True)

#             while True:
#                 try:
#                     replayer.step_forward(multi_hand=True)
#                 except StopIteration:
#                     break

#             replayer.controller.log.save_to_file(fn,
#                                                  player='all',
#                                                  indent=True,
#                                                  notes=replayer.__notes__,)
