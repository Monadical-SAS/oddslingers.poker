
from django.conf import settings
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from banker.mutations import buy_chips

from sockets.models import Socket

from oddslingers.mutations import execute_mutations

from poker.models import PokerTable
from poker.tablebeat import (
    stop_tablebeat,
    start_tablebeat,
    tablebeat_loop,
    queue_tablebeat_dispatch,
    pop_tablebeat_dispatch,
    peek_tablebeat_dispatch,
)
from poker.botbeat import botbeat_loop
from poker.heartbeat_utils import redis_has_dispatch
from poker.tests.test_controller import GenericTableTest
from poker.constants import HIDE_TABLES_AFTER_N_HANDS, PlayingState
from poker.controllers import controller_for_table


class HeartbeatTest(TransactionTestCase):
    def setUp(self):
        self.table = PokerTable.objects.create_table(name='Test Table')
        User = get_user_model()
        self.user = User.objects.create_user(
            username='pirate',
            email='nick@hello.com',
            password='banana',
        )
        self.balance_transfer = buy_chips(self.user, 1000)
        execute_mutations(self.balance_transfer)
        self.mock_socket = Socket.objects.create(
            path=self.table.path,
            active=True,
            channel_name="mock"
        )

    def tearDown(self):
        stop_tablebeat(self.table)
        del self.balance_transfer
        self.table.delete()
        self.user.delete()
        while pop_tablebeat_dispatch(self.table.id):
            pass

    # TODO: figure out how to unit test double forking without sharing
    #   in-memory db connection
    # def test_01_heartbeat_daemonize(self):
    #     got_fork_syscall = False
    #     try:
    #         start_tablebeat(self.table, fork=False)
    #     except SystemExit:
    #         got_fork_syscall = True

    #     assert got_fork_syscall, 'Heartbeat command failed to double fork.'

    def test_table_queue(self):
        stop_tablebeat(self.table)

        # test just the queue part, separate from the heartbeat
        test_action = {'type': 'TEST_ACTION', 'id': self.table.short_id}
        for idx in range(1000):
            queue_tablebeat_dispatch(
                self.table.id,
                {**test_action, 'idx': idx},
            )

        expected = {**test_action, 'idx': 0}
        assert peek_tablebeat_dispatch(self.table.id) == expected, (
            'Event on top of queue does not equal the first '
            'queued test event.'
        )

        assert all(
            pop_tablebeat_dispatch(self.table.id) == {
                **test_action,
                'idx': idx
            }
            for idx in range(1000)
        ), 'Popped action was not equal to queued action.'

    def test_tablebeat_loop(self):
        """
        test a synchronous heartbeat loop, confirm action dispatched properly
        """
        queue_tablebeat_dispatch(self.table.id, {
            'type': 'JOIN_TABLE',
            'user_id': self.user.id,
            'buyin_amt': 100,
        })

        tablebeat_loop(self.table.id, loop=False, verbose=False)

        # check to make sure the heartbeat properly handled the queued event
        self.table.refresh_from_db()
        assert self.table.player_set.filter(user_id=self.user.id).exists(), (
            'Player was not added to the table after'
            'queueing a JOIN_TABLE action.'
        )

    def test_full_heartbeat(self):
        """
        test a synchronous tablebeat_entrypoint, confirm
        action dispatched properly
        """
        # queue a TAKE_SEAT EVENT
        take_seat_event = {
            'type': 'JOIN_TABLE',
            'user_id': str(self.user.id)
        }
        queue_tablebeat_dispatch(self.table.id, take_seat_event)
        start_tablebeat(self.table)

        # check to make sure the heartbeat properly handled the queued event
        self.table.refresh_from_db()
        assert self.table.player_set.filter(user_id=self.user.id).exists(), (
            'Player was not added to the table'
            'after queueing a JOIN_TABLE action.')


@override_settings(POKER_AI_INSTANT=True, HEARTBEAT_POLL=1)
class TablebeatWithBotbeatTest(GenericTableTest):
    def setUp(self):
        super().setUp()

        for player in self.players:
            player.user.is_robot = True
            player.auto_rebuy = 200
            player.save()
            player.user.save()

            execute_mutations(
                buy_chips(player.user, 100000)
            )

        self.table.hand_number = HIDE_TABLES_AFTER_N_HANDS - 2
        self.table.save()

        self.setup_hand(
            blinds_positions={
                'btn_pos': 1,  # cuttlefish
                'sb_pos': 2,  # ajfenix
                'bb_pos': 3,  # cowpig
            },
            add_log=True
        )

        self.alexeimartov = get_user_model().objects.create_user(
            username='alexeimartov',
            email='marty@hello.com',
            password='banana',
            sit_behaviour=PlayingState.SITTING_OUT,
        )
        self.redis_key = f'{settings.REDIS_TABLEBEAT_KEY}-{self.table.id}'
        execute_mutations(
            buy_chips(self.alexeimartov, 10000)
        )

    def tearDown(self):
        super().tearDown()

    def test_tablebeat_in_tutorial(self):
        self.socket = Socket.objects.create(
            user=self.alexeimartov,
            channel_name=f'test_channel_{self.alexeimartov.username}',
            path=self.table.path,
            active=True,
            last_ping=timezone.now(),
        )
        self.table.is_tutorial = True
        self.table.save()

        # tutorial is only robots but there is an active socket
        botbeat_loop(loop=False, stupid=True, verbose=False)
        status = tablebeat_loop(table_id=self.table.id, loop=False)
        assert status == None, (
            'In tutorial with active sockets, tablebeat_loop should not pause'
        )
        self.table.refresh_from_db()

        queue_tablebeat_dispatch(self.table.id, {
            'type': 'JOIN_TABLE',
            'user_id': self.alexeimartov.id,
            'buyin_amt': 100,
        })

        botbeat_loop(loop=False, stupid=True, verbose=False)
        status = tablebeat_loop(table_id=self.table.id, loop=False)
        assert status == None, (
            'In tutorial with active sockets, tablebeat_loop should not pause'
        )
        self.table.refresh_from_db()

        self.socket.active = False
        self.socket.save()

        botbeat_loop(loop=False, stupid=True, verbose=False)
        status = tablebeat_loop(table_id=self.table.id, loop=False)
        assert status == 'paused', (
            'In tutorial without active sockets,tablebeat_loop should pause'
        )

    def test_tablebeat_with_botbeat(self):
        # game only has robots, tablebeat_loop won't do anything yet
        botbeat_loop(loop=False, stupid=True, verbose=False)
        status = tablebeat_loop(table_id=self.table.id, loop=False)
        assert status == 'paused', (
            'With only bots at table, tablebeat_loop should pause.'
        )
        self.table.refresh_from_db()

        queue_tablebeat_dispatch(self.table.id, {
            'type': 'JOIN_TABLE',
            'user_id': self.alexeimartov.id,
            'buyin_amt': 100,
        })
        while self.table.hand_number < HIDE_TABLES_AFTER_N_HANDS:
            botbeat_loop(loop=False, stupid=True, verbose=False)
            if redis_has_dispatch(self.redis_key):
                status = tablebeat_loop(table_id=self.table.id, loop=False)
            else:
                status = tablebeat_loop(table_id=self.table.id, loop=False, peek=False)
            assert status != 'paused', (
                'With a human sitting, tablebeat_loop should not pause.'
            )
            self.table.refresh_from_db()

        alex_player = self.accessor.player_by_user_id(self.alexeimartov.id)
        queue_tablebeat_dispatch(self.table.id, {
            'type': 'LEAVE_SEAT',
            'player_id': alex_player.id,
        })
        while self.table.hand_number < HIDE_TABLES_AFTER_N_HANDS + 30:
            botbeat_loop(loop=False, stupid=True, verbose=False)
            if redis_has_dispatch(self.redis_key):
                status = tablebeat_loop(table_id=self.table.id, loop=False)
            else:
                status = tablebeat_loop(table_id=self.table.id, loop=False, peek=False)
            assert status != 'paused', (
                'after enough hands, game plays out '
                'until everyone leaves'
            )
            self.table.refresh_from_db()
            ctrl = controller_for_table(self.table)
            if len(ctrl.accessor.seated_players()) == 0:
                break

        self.table.refresh_from_db()
        ctrl = controller_for_table(self.table)
        assert len(ctrl.accessor.seated_players()) == 0, (
            'after 30 more hands, the game should be empty'
        )




