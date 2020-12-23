import re
import json

from datetime import timedelta

from channels import route_class
from channels.test import ChannelTestCase, WSClient, Client, apply_routes

from django.contrib.auth import get_user_model

from oddslingers.utils import to_json_str

from .models import Socket
from .handlers import RoutedSocketHandler
from .router import SocketRouter

from .constants import (
    PING_RESPONSE_TYPE,
    HELLO_TYPE,
    GOT_HELLO_TYPE,
    RECONNECT_TYPE,
    ROUTING_KEY,
)

def build_response(key):
    return {
        ROUTING_KEY: key,
        'USER_ID': None,
        'USERNAME': None,
    }


def build_msg(key, path='/t/1/'):
    return {
        'path': path,
        'text': to_json_str({ROUTING_KEY: key}),
    }


class RoutedSocketHandlerTests(ChannelTestCase):
    def test_standard_use(self):
        class TestRoutedSocketHandler(RoutedSocketHandler):
            routes = (
                *RoutedSocketHandler.routes,
                ('TEST_MSG', 'on_string_key'),
                (re.compile('PATTERN_.*'), 'on_regex_key'),
            )

            def connect(self, message, **kwargs):
                self.got_connect = True

            def on_string_key(self, content):
                self.got_test_msg = content

            def on_regex_key(self, content):
                self.got_pattern = content

            def default_route(self, content):
                self.got_default = content

            def disconnect(self, message, **kwargs):
                self.got_disconnect = True


        with apply_routes([route_class(TestRoutedSocketHandler, path='/t/.*/')]):
            ws = Client()

            handler = ws.send_and_consume(
                'websocket.connect',
                {'path': '/t/1/'}
            )
            self.assertEqual(handler.got_connect, True)

            # test plain string route
            message = {
                'path': '/t/1/',
                'text': to_json_str({ROUTING_KEY: 'TEST_MSG'})
            }
            handler = ws.send_and_consume('websocket.receive', message)
            self.assertEqual(handler.got_test_msg[ROUTING_KEY], 'TEST_MSG')

            # test regex route
            message = {
                'path': '/t/1/',
                'text': to_json_str({ROUTING_KEY: 'PATTERN_ABC'})
            }
            handler = ws.send_and_consume('websocket.receive', message)
            self.assertEqual(handler.got_pattern[ROUTING_KEY], 'PATTERN_ABC')

            # test default route
            message = {
                'path': '/t/1/',
                'text': to_json_str({ROUTING_KEY: 'XYZabc123'})
            }
            handler = ws.send_and_consume('websocket.receive', message)
            self.assertEqual(handler.got_default[ROUTING_KEY], 'XYZabc123')

            handler = ws.send_and_consume(
                'websocket.disconnect',
                {'path': '/t/1/'},
            )
            self.assertEqual(handler.got_disconnect, True)


    def test_unknown_key_response(self):
        with apply_routes([route_class(RoutedSocketHandler, path='/t/.*/')]):
            ws = Client()
            message = {'path': '/t/1/', 'text': '{"type": "XYZabc123"}'}
            ws.send_and_consume('websocket.receive', message)
            reply = json.loads(ws.receive()['text'])
            assert reply[ROUTING_KEY] == 'ERROR', (
                'Failed to get error response for unknown message')

    def test_hello_response(self):
        with apply_routes([route_class(RoutedSocketHandler, path='/t/.*/')]):
            ws = Client()
            message = {
                'path': '/t/1/',
                'text': to_json_str({ROUTING_KEY: HELLO_TYPE})
            }
            ws.send_and_consume('websocket.receive', message)

            reply = json.loads(ws.receive()['text'])

            assert reply[ROUTING_KEY] == GOT_HELLO_TYPE, (
                'Failed to get GOT_HELLO_TYPE response to HELLO')

            expected_keys = (
                'user_id',
                'path',
                'TIMESTAMP',
            )

            assert all(key in reply for key in expected_keys)

    def test_ping(self):
        with apply_routes([route_class(RoutedSocketHandler, path='/t/.*/')]):
            ws = Client()
            message = {
                'path': '/t/1/',
                'text': to_json_str({ROUTING_KEY: HELLO_TYPE})
            }
            handler = ws.send_and_consume('websocket.receive', message)

            # set the socket to inactive manually
            handler.socket.active = False
            handler.socket.save()

            assert not handler.socket.active

            # ping response to backend should set the socket back to active
            message = {
                'path': '/t/1/',
                'text': to_json_str({ROUTING_KEY: PING_RESPONSE_TYPE})
            }
            handler = ws.send_and_consume('websocket.receive', message)

            assert handler.socket.active, ('Socket was not set to active after '
                                        'receiving ping response from frontend')


    def test_user_not_logged_in(self):
        class TestRoutedSocketHandler(RoutedSocketHandler):
            login_required = True

        with apply_routes([route_class(TestRoutedSocketHandler, path='/t/.*/')]):
            ws = WSClient()
            ws.send_and_consume('websocket.connect', {'path': '/t/2/'})
            ws.send_and_consume(
                'websocket.receive',
                build_msg('ACTION_THAT_NEEDS_AUTH', path='/t/2/')
            )

            reply = ws.receive()

            assert reply[ROUTING_KEY] == RECONNECT_TYPE, (
                'Failed to get RECONNECT_TYPE when user not authenticated.')


    def test_user_logged_in(self):
        class TestRoutedSocketHandler(RoutedSocketHandler):
            login_required = True

        User = get_user_model()
        user = User.objects.create_user(
            username='test_user',
            email='',
            password='123',
        )
        ws = WSClient()
        ws.force_login(user)

        with apply_routes([route_class(TestRoutedSocketHandler, path='/t/.*')]):
            ws.send_and_consume('websocket.connect', {'path': '/t/3/'})

            handler = ws.send_and_consume(
                'websocket.receive',
                build_msg(HELLO_TYPE, path='/t/3/')
            )

            assert handler.message.user and handler.message.user == user, (
                'Handler.user was wrong when we received logged in user\'s msg')

            reply = ws.receive()

            assert reply[ROUTING_KEY] == GOT_HELLO_TYPE, (
                "Failed to get response to logged in user's HELLO")


class SocketRouterTests(ChannelTestCase):
    def test_socket_router(self):
        class TestView:
            socket = SocketRouter(handler=RoutedSocketHandler)

            @socket.connect
            def on_connect(self, message):
                self.got_connect = True

            @socket.route('TEST_MSG')
            def on_string_key(self, content):
                self.got_test_msg = content

            @socket.route(re.compile('PATTERN_.*'))
            def on_regex_key(self, content):
                self.got_pattern = content

            @socket.default_route
            def on_unknown_key(self, content):
                self.got_default = content

            @socket.disconnect
            def on_disconnect(self, message):
                self.got_disconnect = True

        with apply_routes([route_class(TestView.socket.Handler, path='/t/.*/')]):
            ws = Client()

            # test connect
            handler = ws.send_and_consume(
                'websocket.connect',
                {'path': '/t/1/'}
            )

            assert handler.got_connect

            # test plain string route
            handler = ws.send_and_consume(
                'websocket.receive',
                build_msg('TEST_MSG'),
            )
            assert handler.got_test_msg[ROUTING_KEY] == 'TEST_MSG'

            # test regex route
            handler = ws.send_and_consume(
                'websocket.receive',
                build_msg('PATTERN_ABC'),
            )
            assert handler.got_pattern[ROUTING_KEY] == 'PATTERN_ABC'

            # test default route
            handler = ws.send_and_consume(
                'websocket.receive',
                build_msg('XYZabc123'),
            )
            assert handler.got_default[ROUTING_KEY] == 'XYZabc123'

            # test disconnect
            handler = ws.send_and_consume(
                'websocket.disconnect',
                {'path': '/t/1/'}
            )
            assert handler.got_disconnect


class SocketModelTests(ChannelTestCase):
    def test_socket_model_lifecycle(self):
        with apply_routes([route_class(RoutedSocketHandler, path='/t/.*/')]):
            ws = Client()

            handler = ws.send_and_consume(
                'websocket.connect',
                {'path': '/t/1/'}
            )

            assert handler.socket.id
            assert handler.socket.active
            assert handler.socket.last_ping
            assert handler.socket.user is None
            assert handler.socket.channel_name == ws.reply_channel

            existing_socket_id = handler.socket.id
            handler = ws.send_and_consume(
                'websocket.receive',
                build_msg('XYZabc123')
            )

            assert handler.socket.id == existing_socket_id, (
                'New Socket object was created for by websocket.recv '
                'instead of using the existing websocket.connect one')

            handler = ws.send_and_consume(
                'websocket.disconnect',
                {'path': '/t/1/'}
            )

            # make sure socket is deleted on disconnect
            assert handler.socket.id is None, (
                'Socket was not deleted on disconnect')

    def test_cleanup_stale(self):
        with apply_routes([route_class(RoutedSocketHandler, path='/t/.*/')]):
            ws = Client()
            handler = ws.send_and_consume(
                'websocket.connect',
                {'path': '/t/1/'}
            )
            socket = handler.socket
            assert socket.id and socket.active, (
                'Socket object was not created by a websocket.connect')

            # make sure socket is marked inactive on cleanup_stale()
            Socket.objects.all().cleanup_stale()
            socket.refresh_from_db()
            assert not socket.active, (
                'Socket was not marked inactive after missing a PING')

            # make sure socket is deleted on purge_inactive()
            socket.last_ping = socket.last_ping - timedelta(hours=1)
            socket.save()
            Socket.objects.all().purge_inactive()
            assert not Socket.objects.filter(id=socket.id).exists(), (
                'Inactive Socket was not deleted by purge_inactive()')
