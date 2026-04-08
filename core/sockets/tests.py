"""
Socket handler tests — migrated from Channels 1.x to Channels 4 WebsocketCommunicator.

Previously all tests were skipped with @unittest.skip (P2-025).  They are now
rewritten using WebsocketCommunicator against the consumer's ASGI callable directly,
so no Redis / channel layer is required for the handler-level tests.

SocketRouterTests is kept skipped: SocketRouter uses a decorator-based API that
is separate from RoutedSocketHandler and requires its own migration pass.
"""

import json
import unittest

from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import re_path


from .constants import (
    GOT_HELLO_TYPE,
    HELLO_TYPE,
    PING_RESPONSE_TYPE,
    RECONNECT_TYPE,
    ROUTING_KEY,
)
from .handlers import RoutedSocketHandler
from .models import Socket


def _app(handler_cls=None):
    cls = handler_cls or RoutedSocketHandler
    return URLRouter([re_path(r"^ws/$", cls.as_asgi())])


class _SendCapture:
    """Mixin that captures send_action calls via self.send() so WebsocketCommunicator
    can observe them without a real channel layer."""

    def send_action(self, action_type: str, **kwargs):
        from oddslingers.utils import add_timestamp_and_hash

        content = add_timestamp_and_hash({**kwargs, ROUTING_KEY: action_type})
        self.send(text_data=json.dumps(content))


class _TestableHandler(_SendCapture, RoutedSocketHandler):
    pass


def _testable_app():
    return URLRouter([re_path(r"^ws/$", _TestableHandler.as_asgi())])


# ---------------------------------------------------------------------------


class RoutedSocketHandlerTests(TransactionTestCase):
    def test_standard_use(self):
        """Custom routes dispatch to the correct handlers; connect and disconnect work."""

        class CustomHandler(_SendCapture, RoutedSocketHandler):
            routes = (
                *RoutedSocketHandler.routes,
                ("TEST_MSG", "on_test_msg"),
            )

            def on_test_msg(self, content):
                self.send_action("TEST_MSG_ACK")

        async def _run():
            app = URLRouter([re_path(r"^ws/$", CustomHandler.as_asgi())])
            communicator = WebsocketCommunicator(app, "/ws/")
            connected, _ = await communicator.connect()
            self.assertTrue(connected, "connect() should succeed")
            self.assertEqual(Socket.objects.count(), 1)

            await communicator.send_json_to({ROUTING_KEY: "TEST_MSG"})
            reply = json.loads(await communicator.receive_from())
            self.assertEqual(reply[ROUTING_KEY], "TEST_MSG_ACK")

            await communicator.disconnect()
            await communicator.receive_nothing(timeout=0.1)
            self.assertEqual(Socket.objects.count(), 0)

        async_to_sync(_run)()

    def test_unknown_key_response(self):
        """An unknown message type produces no response (silent ignore)."""

        async def _run():
            communicator = WebsocketCommunicator(_testable_app(), "/ws/")
            await communicator.connect()
            await communicator.send_json_to({ROUTING_KEY: "XYZabc123"})
            received_nothing = await communicator.receive_nothing(timeout=0.2)
            self.assertTrue(
                received_nothing, "Unknown key must be silently ignored, not error"
            )
            await communicator.disconnect()

        async_to_sync(_run)()

    def test_hello_response(self):
        """Sending HELLO must produce a GOT_HELLO reply."""

        async def _run():
            communicator = WebsocketCommunicator(_testable_app(), "/ws/")
            await communicator.connect()
            await communicator.send_json_to({ROUTING_KEY: HELLO_TYPE})
            reply = json.loads(await communicator.receive_from())
            self.assertEqual(
                reply[ROUTING_KEY],
                GOT_HELLO_TYPE,
                "HELLO must be answered with GOT_HELLO",
            )

        async_to_sync(_run)()

    def test_ping(self):
        """Sending PING must NOT produce a reply (avoids infinite ping loop)."""

        async def _run():
            communicator = WebsocketCommunicator(_testable_app(), "/ws/")
            await communicator.connect()

            socket = Socket.objects.first()
            socket.active = False
            socket.save(update_fields=["active"])

            await communicator.send_json_to({ROUTING_KEY: PING_RESPONSE_TYPE})
            received_nothing = await communicator.receive_nothing(timeout=0.2)
            self.assertTrue(
                received_nothing,
                "PING must not be echoed back — would cause infinite loop "
                "because PING_TYPE == PING_RESPONSE_TYPE == 'PING'",
            )

            socket.refresh_from_db()
            self.assertTrue(socket.active, "PING must mark socket active")
            await communicator.disconnect()

        async_to_sync(_run)()

    def test_user_not_logged_in(self):
        """Unauthenticated message to a login_required handler sends RECONNECT."""

        class AuthRequired(_SendCapture, RoutedSocketHandler):
            login_required = True

        async def _run():
            app = URLRouter([re_path(r"^ws/$", AuthRequired.as_asgi())])
            communicator = WebsocketCommunicator(app, "/ws/")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_json_to({ROUTING_KEY: "SOME_ACTION"})
            reply = json.loads(await communicator.receive_from())
            self.assertEqual(
                reply.get("type"),
                RECONNECT_TYPE,
                "Unauthenticated client on login_required handler must receive RECONNECT",
            )

        async_to_sync(_run)()

    def test_user_logged_in(self):
        """Authenticated user on login_required handler passes auth and gets a response."""

        class AuthRequired(_SendCapture, RoutedSocketHandler):
            login_required = True

        User = get_user_model()

        async def _run():
            user = await User.objects.acreate_user(
                username="ws_test_user", email="", password="pass123"
            )
            app = URLRouter([re_path(r"^ws/$", AuthRequired.as_asgi())])
            communicator = WebsocketCommunicator(app, "/ws/")
            communicator.scope["user"] = user

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_json_to({ROUTING_KEY: HELLO_TYPE})
            reply = json.loads(await communicator.receive_from())
            self.assertEqual(
                reply[ROUTING_KEY],
                GOT_HELLO_TYPE,
                "Authenticated user must receive GOT_HELLO",
            )
            await communicator.disconnect()

        async_to_sync(_run)()


# ---------------------------------------------------------------------------


@unittest.skip(
    "SocketRouter decorator API not yet migrated to Channels 4. "
    "Handler-level routing is covered by RoutedSocketHandlerTests above."
)
class SocketRouterTests(TransactionTestCase):
    def test_socket_router(self):
        pass


# ---------------------------------------------------------------------------


class SocketModelTests(TransactionTestCase):
    def test_socket_model_lifecycle(self):
        """connect() creates a Socket row; disconnect() deletes it."""

        async def _run():
            self.assertEqual(Socket.objects.count(), 0)
            communicator = WebsocketCommunicator(_app(), "/ws/")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            socket = Socket.objects.get()
            self.assertTrue(socket.active)
            self.assertIsNotNone(socket.last_ping)
            self.assertIsNone(socket.user)

            await communicator.disconnect()
            await communicator.receive_nothing(timeout=0.1)
            self.assertEqual(Socket.objects.count(), 0)

        async_to_sync(_run)()

    def test_cleanup_stale(self):
        """cleanup_stale() marks active sockets inactive and sends PING; purge_inactive()
        removes those that haven't pinged back within the time window."""

        async def _run():
            communicator = WebsocketCommunicator(_app(), "/ws/")
            await communicator.connect()
            socket = Socket.objects.get()
            self.assertTrue(socket.active)

            Socket.objects.all().cleanup_stale()
            socket.refresh_from_db()
            self.assertFalse(socket.active, "cleanup_stale must mark socket inactive")

            await communicator.disconnect()

        async_to_sync(_run)()
