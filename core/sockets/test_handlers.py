"""
Tests for RoutedSocketHandler (Channels 4 WebsocketConsumer).

Uses WebsocketCommunicator directly against the consumer's ASGI callable so
the channel layer is never involved.  Requires TransactionTestCase so that
DB writes inside the consumer's thread pool are visible to assertions.
"""

import json

from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from django.urls import re_path
from unittest.mock import patch

from .constants import ROUTING_KEY
from .handlers import RoutedSocketHandler
from .models import Socket


def _app(handler_cls=None):
    """Build a minimal URLRouter wrapping the given handler (default: RoutedSocketHandler)."""
    cls = handler_cls or RoutedSocketHandler
    return URLRouter([re_path(r"^ws/$", cls.as_asgi())])


class PingHandlerTests(TransactionTestCase):
    """on_ping must update last_ping without echoing back to the client."""

    def test_ping_does_not_echo(self):
        """Sending PING must produce zero outbound messages (no infinite loop)."""

        async def _run():
            communicator = WebsocketCommunicator(_app(), "/ws/")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_json_to({ROUTING_KEY: "PING"})

            # No response should arrive within the timeout.
            received_nothing = await communicator.receive_nothing(timeout=0.2)
            self.assertTrue(
                received_nothing,
                "on_ping sent a reply — this causes an infinite ping-pong loop "
                "because PING_TYPE == PING_RESPONSE_TYPE == 'PING'",
            )
            await communicator.disconnect()

        async_to_sync(_run)()

    def test_ping_marks_socket_active(self):
        """Sending PING while socket is inactive must set active=True and refresh last_ping."""

        async def _run():
            communicator = WebsocketCommunicator(_app(), "/ws/")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Force socket inactive so we can observe the ping activating it.
            socket = Socket.objects.get(channel_name__isnull=False)
            socket.active = False
            socket.save(update_fields=["active"])

            await communicator.send_json_to({ROUTING_KEY: "PING"})
            # Give the sync thread a moment to complete.
            await communicator.receive_nothing(timeout=0.2)

            socket.refresh_from_db()
            self.assertTrue(socket.active, "PING should set socket.active = True")
            await communicator.disconnect()

        async_to_sync(_run)()


class ConnectDisconnectTests(TransactionTestCase):
    """connect() and disconnect() Socket lifecycle."""

    def test_connect_creates_socket(self):
        """A successful connect must create a Socket DB row."""

        async def _run():
            self.assertEqual(Socket.objects.count(), 0)
            communicator = WebsocketCommunicator(_app(), "/ws/")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            self.assertEqual(Socket.objects.count(), 1)
            await communicator.disconnect()

        async_to_sync(_run)()

    def test_disconnect_deletes_socket(self):
        """Disconnecting must delete the Socket DB row."""

        async def _run():
            communicator = WebsocketCommunicator(_app(), "/ws/")
            await communicator.connect()
            self.assertEqual(Socket.objects.count(), 1)
            await communicator.disconnect()
            # Give the sync thread a moment to complete.
            await communicator.receive_nothing(timeout=0.2)
            self.assertEqual(Socket.objects.count(), 0)

        async_to_sync(_run)()

    def test_connect_db_failure_does_not_accept(self):
        """If setup_session raises, the connection must be rejected (not accepted)."""

        async def _run():
            with patch.object(
                RoutedSocketHandler,
                "setup_session",
                side_effect=Exception("DB down"),
            ):
                communicator = WebsocketCommunicator(_app(), "/ws/")
                connected, code = await communicator.connect()
                # Connection should be closed/rejected when session setup fails.
                self.assertFalse(
                    connected,
                    "connect() should reject the WebSocket when setup_session raises",
                )

        async_to_sync(_run)()


class RoutingTests(TransactionTestCase):
    """Message routing: known types are dispatched, unknown types are silently dropped."""

    def test_unknown_message_type_no_crash(self):
        """Sending an unknown message type must not crash or produce an error response."""

        async def _run():
            communicator = WebsocketCommunicator(_app(), "/ws/")
            await communicator.connect()
            await communicator.send_json_to({ROUTING_KEY: "TOTALLY_UNKNOWN_XYZ"})
            received_nothing = await communicator.receive_nothing(timeout=0.2)
            self.assertTrue(
                received_nothing,
                "Unknown message type should be silently ignored, not crash",
            )
            await communicator.disconnect()

        async_to_sync(_run)()

    def test_missing_routing_key_no_crash(self):
        """Messages without a routing key must be silently dropped."""

        async def _run():
            communicator = WebsocketCommunicator(_app(), "/ws/")
            await communicator.connect()
            await communicator.send_json_to({"some_other_field": "value"})
            received_nothing = await communicator.receive_nothing(timeout=0.2)
            self.assertTrue(received_nothing, "Missing routing key should not crash")
            await communicator.disconnect()

        async_to_sync(_run)()

    def test_invalid_json_no_crash(self):
        """Non-JSON text must be silently dropped without crashing."""

        async def _run():
            communicator = WebsocketCommunicator(_app(), "/ws/")
            await communicator.connect()
            await communicator.send_to(text_data="not json at all {{{{")
            received_nothing = await communicator.receive_nothing(timeout=0.2)
            self.assertTrue(received_nothing, "Invalid JSON should be silently ignored")
            await communicator.disconnect()

        async_to_sync(_run)()


class AuthenticationTests(TransactionTestCase):
    """login_required enforces auth at the message level."""

    def test_unauthenticated_message_on_login_required_handler(self):
        """An unauthenticated client sending a message to a login_required handler
        must receive RECONNECT and have the connection closed."""

        class AuthRequired(RoutedSocketHandler):
            login_required = True

        async def _run():
            communicator = WebsocketCommunicator(_app(AuthRequired), "/ws/")
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_json_to({ROUTING_KEY: "SOME_ACTION"})

            response = await communicator.receive_from()
            data = json.loads(response)
            self.assertEqual(
                data.get("type"),
                "RECONNECT",
                "login_required handler should send RECONNECT to unauthenticated client",
            )
            await communicator.disconnect()

        async_to_sync(_run)()


class TrustedProxyTests(TransactionTestCase):
    """_is_trusted_proxy must only honour X-Real-IP from known proxy IPs.

    NOTE: _is_trusted_proxy reads the module-level _TRUSTED_NETWORKS list
    (pre-parsed at import time), not settings.TRUSTED_PROXY_CIDRS directly.
    Tests must patch sockets.handlers._TRUSTED_NETWORKS, not settings.
    """

    def test_trusted_ip_accepted(self):
        import ipaddress
        from sockets.handlers import _is_trusted_proxy

        with patch(
            "sockets.handlers._TRUSTED_NETWORKS", [ipaddress.ip_network("10.0.0.0/8")]
        ):
            self.assertTrue(_is_trusted_proxy("10.0.1.50"))

    def test_untrusted_ip_rejected(self):
        import ipaddress
        from sockets.handlers import _is_trusted_proxy

        with patch(
            "sockets.handlers._TRUSTED_NETWORKS", [ipaddress.ip_network("10.0.0.0/8")]
        ):
            self.assertFalse(_is_trusted_proxy("203.0.113.1"))

    def test_empty_cidr_list_rejects_all(self):
        from sockets.handlers import _is_trusted_proxy

        with patch("sockets.handlers._TRUSTED_NETWORKS", []):
            self.assertFalse(_is_trusted_proxy("10.0.0.1"))

    def test_x_real_ip_stored_from_trusted_proxy(self):
        """X-Real-IP is stored as user_ip when the connection arrives from a trusted proxy."""
        import ipaddress

        async def _run():
            communicator = WebsocketCommunicator(
                _app(),
                "/ws/",
                headers=[(b"x-real-ip", b"1.2.3.4")],
            )
            communicator.scope["client"] = ("10.0.0.1", 12345)
            with patch(
                "sockets.handlers._TRUSTED_NETWORKS",
                [ipaddress.ip_network("10.0.0.0/8")],
            ):
                connected, _ = await communicator.connect()
            self.assertTrue(connected)
            socket = Socket.objects.first()
            self.assertEqual(socket.user_ip, "1.2.3.4")
            await communicator.disconnect()

        async_to_sync(_run)()

    def test_x_real_ip_ignored_from_untrusted_client(self):
        """A forged X-Real-IP from an untrusted client must not be stored."""
        import ipaddress

        async def _run():
            communicator = WebsocketCommunicator(
                _app(),
                "/ws/",
                headers=[(b"x-real-ip", b"9.9.9.9")],
            )
            communicator.scope["client"] = ("203.0.113.55", 12345)
            with patch(
                "sockets.handlers._TRUSTED_NETWORKS",
                [ipaddress.ip_network("10.0.0.0/8")],
            ):
                connected, _ = await communicator.connect()
            self.assertTrue(connected)
            socket = Socket.objects.first()
            self.assertEqual(
                socket.user_ip,
                "203.0.113.55",
                "Forged X-Real-IP from untrusted client must not be stored",
            )
            await communicator.disconnect()

        async_to_sync(_run)()
