from collections import defaultdict

from django.utils import timezone
from django.contrib.auth import get_user_model

from banker.mutations import buy_chips
from sockets.models import Socket, SocketQuerySet

from oddslingers.mutations import execute_mutations

from poker.subscribers import AnimationSubscriber
from poker.megaphone import (
    table_sockets,
    player_sockets,
    spectator_sockets,
    gamestates_for_sockets,
    get_players_from_animations,
    gamestate_json
)

from .test_controller import GenericTableTest


class SocketTest(GenericTableTest):
    def setUp(self):
        super().setUp()
        User = get_user_model()

        self.spectator1 = User.objects.create_user(
            username='spectator1',
            email='spectator1@example.com',
            password='banana',
        )
        self.spectator2 = User.objects.create_user(
            username='spectator2',
            email='spectator2@example.com',
            password='banana',
        )

        self.spectators = [self.spectator1, self.spectator2]

        self.sockets = []

        for player in self.players:
            self.sockets.append(Socket.objects.create(
                user=player.user,
                channel_name=f'test_channel_{player.username}',
                path=self.table.path,
                active=True,
                last_ping=timezone.now(),
            ))

        for user in self.spectators:
            self.sockets.append(Socket.objects.create(
                user=user,
                channel_name=f'test_channel_{user.username}',
                path=self.table.path,
                active=True,
                last_ping=timezone.now(),
            ))

    def tearDown(self):
        for spectator in self.spectators:
            spectator.delete()
        for player in self.players:
            player.user.delete()
        super().tearDown()


class MegaphoneSocketTest(SocketTest):
    def test_table_sockets(self):
        table_socket_ids = list(
            table_sockets(self.table).order_by('id')
                                     .values_list('id', flat=True)
        )
        socket_ids = list(sorted(socket.id for socket in self.sockets))

        assert table_socket_ids == socket_ids, \
                'table_sockets(table) did not match the sockets '\
                'created by the test for this table'

    def test_player_sockets(self):
        for player in self.players:
            method1 = list(
                player.sockets
                      .order_by('id')
                      .values_list('id', flat=True)
            )
            method2 = list(
                player_sockets(player).order_by('id')
                                      .values_list('id', flat=True)
            )
            assert method1 == method2

            assert all(
                socket.user_id == player.user_id
                for socket in player_sockets(player)
            ), 'Some sockets returned by player_sockets() were not '\
               'owned by the player\'s user'

            assert all(
                socket.path == self.table.path
                for socket in player_sockets(player)
            ),  'Some sockets returned by player_sockets() were not '\
                'attached to the player\'s table'

    def test_spectator_sockets(self):
        spectator_socket_ids = list(
            spectator_sockets(self.table).order_by('id')
                                         .values_list('id', flat=True)
        )
        socket_ids = list(
            Socket.objects
                  .filter(user__in=self.spectators)
                  .order_by('id')
                  .values_list('id', flat=True)
            )

        assert spectator_socket_ids == socket_ids, (
            'spectator_sockets(table) did not match the spectator '
            'sockets created by the test for this table')

    def test_socket_collection_methods(self):
        private_socket_ids = set()
        for player in self.table.player_set.all():
            private_socket_ids |= set(player.sockets
                                            .values_list('id', flat=True))

        spectator_socket_ids = set(self.table
                                       .sockets
                                       .exclude(id__in=private_socket_ids)
                                       .order_by('id')
                                       .values_list('id', flat=True))

        assert set(
            spectator_sockets(self.table).values_list('id', flat=True)
        ) == spectator_socket_ids
        assert set(
            Socket.objects
                  .filter(user__in=self.spectators)
                  .values_list('id', flat=True)
        ) == spectator_socket_ids
        assert set(
            table_sockets(self.table).values_list('id', flat=True)
        ) == (set(spectator_socket_ids) | set(private_socket_ids))

        all_player_sockets = set()
        for player in self.players:
            all_player_sockets |= set(
                player_sockets(player).values_list('id', flat=True)
            )

        assert all_player_sockets == set(private_socket_ids)


class MegaphoneGamestateTest(SocketTest):
    def test_private_data_in_gamestate(self):
        self.controller.step()

        socks_and_states = gamestates_for_sockets(
            self.accessor,
            self.controller.subscribers
        )

        next_player = self.accessor.next_to_act()
        next_player_sockets = player_sockets(next_player)

        assert next_player_sockets

        socket_ids = lambda queryset: set(s.id for s in queryset)

        socket_ids_list = [
            socket_ids(socket_qset) for socket_qset in socks_and_states.keys()
        ]

        assert socket_ids(next_player_sockets) in socket_ids_list

        player_gamestate = [
            state for socks, state in socks_and_states.items()
            if socks.filter(user__id=next_player.user.id)
        ]

        assert len(player_gamestate) == 1 and "players" in player_gamestate[0]
        assert 'amt_to_call' in player_gamestate[0]['players'][str(next_player.id)]
        assert 'min_bet' in player_gamestate[0]['players'][str(next_player.id)]

    def test_players_on_animation_gamestate(self):
        self.controller.subscribers = [
            AnimationSubscriber(self.accessor)
        ]
        self.controller.step()
        gamestate = gamestate_json(self.accessor,
                                   None,
                                   self.controller.subscribers)
        retrieved_players = get_players_from_animations(gamestate, self.accessor)

        assert len(retrieved_players) == len(self.players), \
                'Players got from animations are not the same amount' \
                'as the initial players'
        for player in retrieved_players:
            assert player in self.players, \
                    'Got a player that is not in the initial players'


class PrivateBroadcastOnlyOnPassiveActionTest(SocketTest):
    def test_private_broadcast_only_on_passive_action(self):
        messages = defaultdict(list)

        def send_action_patch(self, msg, **kwargs):
            for channel_name in self.values_list('channel_name', flat=True):
                messages[channel_name].append((msg, kwargs))
            return 0

        original_send_action = SocketQuerySet.send_action
        SocketQuerySet.send_action = send_action_patch

        self.controller.step()
        self.controller.dispatch(
            'SIT_OUT_AT_BLINDS',
            player_id=self.pirate_player.id,
            set_to=True
        )

        for socket in self.sockets:
            if socket.channel_name != 'test_channel_pirate':
                assert not messages[socket.channel_name]

            else:
                sent = messages[socket.channel_name]
                assert len(sent) == 1
                assert sent.pop()[1]['privado']

        SocketQuerySet.send_action = original_send_action


class StartingPlayersSocketsTest(SocketTest):
    def test_players_on_animation_gamestate(self):
        """
        All the starting players should have a player socket and not a
        spectator one even if they are not seated at the end of the animation
        sequence
        """
        self.controller.subscribers = [
            AnimationSubscriber(self.accessor)
        ]
        self.controller.broadcast = False
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        self.setup_hand(blinds_positions=blind_pos)

        # self.accessor.describe(True)
        self.controller.dispatch("CALL", player_id=self.pirate_player.id)
        self.controller.dispatch("LEAVE_SEAT", player_id=self.cowpig_player.id)
        self.controller.dispatch("CALL", player_id=self.cuttlefish_player.id)
        self.controller.dispatch("CALL", player_id=self.ajfenix_player.id)

        self.accessor.table.board = ['2h', '2c', '4h', '5h', 'Kd']
        # self.accessor.describe(True)
        self.controller.dispatch("CHECK", player_id=self.ajfenix_player.id)
        self.controller.dispatch("CHECK", player_id=self.pirate_player.id)
        self.controller.dispatch("CHECK", player_id=self.cuttlefish_player.id)
        # self.accessor.describe(True)

        gamestate = gamestate_json(self.accessor,
                                   None,
                                   self.controller.subscribers)
        retrieved_players = get_players_from_animations(gamestate, self.accessor)

        assert self.cowpig_player in retrieved_players

        private_socket_ids = set()
        for player in retrieved_players:
            private_socket_ids |= set(player.sockets
                                            .values_list('id', flat=True))

        expected_socket_ids = set(self.table
                                      .sockets
                                      .exclude(id__in=private_socket_ids)
                                      .order_by('id')
                                      .values_list('id', flat=True))

        spectator_sockets_ = spectator_sockets(self.table, retrieved_players)
        spectator_socket_ids = set(spectator_sockets_.values_list('id',
                                                                  flat=True))
        assert spectator_socket_ids == expected_socket_ids

        spectator_socket_ids = set(Socket.objects
                                         .filter(user__in=self.spectators)
                                         .values_list('id', flat=True))

        assert spectator_socket_ids == expected_socket_ids

        table_socket_ids = set(table_sockets(self.table).values_list('id',
                                                                     flat=True))
        expected_table_sockets = (set(spectator_socket_ids)
                                  | set(private_socket_ids))
        assert table_socket_ids == expected_table_sockets

        assert self.cowpig_player in retrieved_players, \
                'Starting player should be seated at begining gamestate'

        assert self.cowpig_player not in self.accessor.seated_players(), \
                'Starting player shouldn\'t be seated at ending gamestate'


class SitPlayerSocketsTest(SocketTest):
    def test_player_on_animation_gamestate(self):
        """
        All the ending players should have a player socket and not a
        spectator one even if they are not seated at the beginning of the
        animation sequence
        """
        self.controller.subscribers = [
            AnimationSubscriber(self.accessor)
        ]
        self.controller.broadcast = False
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        self.setup_hand(blinds_positions=blind_pos)
        execute_mutations(
            buy_chips(self.spectator1, 1000)
        )

        #self.accessor.describe(True)
        self.controller.dispatch("CALL", player_id=self.pirate_player.id)
        self.controller.dispatch("JOIN_TABLE", user_id=self.spectator1.id)

        gamestate = gamestate_json(self.accessor,
                                   None,
                                   self.controller.subscribers)
        retrieved_players = get_players_from_animations(gamestate, self.accessor)

        spectator1_player = self.accessor.player_by_user_id(self.spectator1.id)

        assert spectator1_player in retrieved_players

        private_socket_ids = set()
        for player in retrieved_players:
            private_socket_ids |= set(player.sockets
                                            .values_list('id', flat=True))

        expected_socket_ids = set(self.table
                                      .sockets
                                      .exclude(id__in=private_socket_ids)
                                      .order_by('id')
                                      .values_list('id', flat=True))

        spectator_sockets_ = spectator_sockets(self.table, retrieved_players)
        spectator_socket_ids = set(spectator_sockets_.values_list('id',
                                                                  flat=True))
        assert spectator_socket_ids == expected_socket_ids

        spectator_socket_ids = set(Socket.objects
                                         .filter(user_id=self.spectator2.id)
                                         .values_list('id', flat=True))

        assert spectator_socket_ids == expected_socket_ids

        table_socket_ids = set(table_sockets(self.table).values_list('id',
                                                                     flat=True))
        expected_table_sockets = (set(spectator_socket_ids)
                                  | set(private_socket_ids))
        assert table_socket_ids == expected_table_sockets

        assert spectator1_player in retrieved_players, \
                'Ending player should be at beginning of gamestate'
