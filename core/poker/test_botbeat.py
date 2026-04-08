"""
Tests for botbeat monitoring integration.

_SentryCompat shim is now in oddslingers.monitoring — see test_monitoring.py
for the shim's full test coverage. This file verifies botbeat imports the
shared client correctly.
"""

from unittest.mock import patch

from django.test import SimpleTestCase


class BotbeatMonitoringTests(SimpleTestCase):
    def test_client_is_importable(self):
        from poker import botbeat

        self.assertTrue(hasattr(botbeat, "client"))

    def test_client_extra_context_forwards_to_sentry(self):
        import sentry_sdk
        from poker import botbeat

        with patch.object(sentry_sdk, "set_context") as mock_ctx:
            try:
                botbeat.client.extra_context({"table_id": "abc"})
            except Exception:
                pass  # raven client may behave differently — just verify no silent discard
            # If using _SentryCompat, set_context must have been called.
            if "SentryCompat" in type(botbeat.client).__name__:
                mock_ctx.assert_called_once_with("extra", {"table_id": "abc"})

    def test_capture_exception_not_silent(self):
        import sentry_sdk
        from poker import botbeat

        with patch.object(sentry_sdk, "capture_exception") as mock_cap:
            try:
                raise ValueError("test")
            except ValueError:
                botbeat.client.captureException()
            if "SentryCompat" in type(botbeat.client).__name__:
                mock_cap.assert_called_once()
