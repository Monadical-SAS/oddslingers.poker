"""
Tests for SocketQuerySet.send_str / _send_all.

Uses an in-memory channel layer so no Redis is required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TransactionTestCase, SimpleTestCase


class SendAllTests(SimpleTestCase):
    """_send_all dispatches concurrently and tolerates per-channel failures."""

    def _run(self, coro):
        from asgiref.sync import async_to_sync

        return async_to_sync(coro)()

    def test_sends_to_all_names(self):
        from sockets.models import _send_all

        layer = MagicMock()
        layer.send = AsyncMock()
        names = ["ch-1", "ch-2", "ch-3"]
        msg = {"type": "websocket.send", "text": "hello"}

        sent = self._run(_send_all(layer, names, msg))

        self.assertEqual(sent, 3)
        self.assertEqual(layer.send.call_count, 3)
        layer.send.assert_any_call("ch-1", msg)
        layer.send.assert_any_call("ch-2", msg)
        layer.send.assert_any_call("ch-3", msg)

    def test_failed_send_does_not_abort_remaining(self):
        """A single failing channel must not prevent messages to other channels."""
        from sockets.models import _send_all

        layer = MagicMock()
        call_count = 0

        async def _send(name, msg):
            nonlocal call_count
            call_count += 1
            if name == "ch-bad":
                raise Exception("channel full")

        layer.send = _send
        names = ["ch-1", "ch-bad", "ch-2"]
        msg = {"type": "websocket.send", "text": "hello"}

        sent = self._run(_send_all(layer, names, msg))

        self.assertEqual(call_count, 3, "all channels should be attempted")
        self.assertEqual(sent, 2, "only successful sends should be counted")

    def test_empty_names_returns_zero(self):
        from sockets.models import _send_all

        layer = MagicMock()
        layer.send = AsyncMock()

        sent = self._run(_send_all(layer, [], {}))

        self.assertEqual(sent, 0)
        layer.send.assert_not_called()


class SocketQuerySetSendStrTests(TransactionTestCase):
    """SocketQuerySet.send_str filters bot channels and uses _send_all."""

    def test_bot_channels_excluded(self):
        """channel names starting with 'bot-' must never be sent to."""

        captured = []

        async def fake_send_all(layer, names, message):
            captured.extend(names)
            return len(names)

        with patch("sockets.models._send_all", side_effect=fake_send_all):
            from sockets.models import SocketQuerySet

            qs = MagicMock(spec=SocketQuerySet)
            qs.values_list = MagicMock(
                return_value=["bot-ai-1", "player-abc", "bot-ai-2", "player-xyz"]
            )
            # Call the real send_str logic via a mock channel layer
            with patch("sockets.models.get_channel_layer", return_value=MagicMock()):
                SocketQuerySet.send_str(qs, "test content")

        self.assertNotIn("bot-ai-1", captured)
        self.assertNotIn("bot-ai-2", captured)
        self.assertIn("player-abc", captured)
        self.assertIn("player-xyz", captured)

    def test_no_channel_layer_returns_zero(self):
        """send_str must return 0 immediately when no channel layer is configured."""
        from sockets.models import SocketQuerySet
        from unittest.mock import MagicMock

        qs = MagicMock(spec=SocketQuerySet)
        with patch("sockets.models.get_channel_layer", return_value=None):
            result = SocketQuerySet.send_str(qs, "hello")

        self.assertEqual(result, 0)
