"""
Tests for oddslingers.monitoring — the raven-compatible sentry_sdk shim.
"""

from unittest.mock import patch

from django.test import SimpleTestCase


class MonitoringClientTests(SimpleTestCase):
    def test_client_is_importable(self):
        from oddslingers.monitoring import client

        self.assertIsNotNone(client)

    def test_extra_context_calls_sentry_set_context(self):
        import sentry_sdk
        from oddslingers.monitoring import client

        with patch.object(sentry_sdk, "set_context") as mock_set:
            client.extra_context({"key": "val"})
            # If raven is installed client is the real raven client — skip assertion.
            # If _SentryCompat is active, set_context must have been called.
            if (
                hasattr(client, "extra_context")
                and "SentryCompat" in type(client).__name__
            ):
                mock_set.assert_called_once_with("extra", {"key": "val"})

    def test_capture_exception_calls_sentry(self):
        import sentry_sdk
        from oddslingers.monitoring import client

        with patch.object(sentry_sdk, "capture_exception") as mock_cap:
            try:
                raise ValueError("test error")
            except ValueError:
                client.captureException()
            if "SentryCompat" in type(client).__name__:
                mock_cap.assert_called_once()
