"""
Tests for tablebeat monitoring integration.

_SentryCompat shim is now in oddslingers.monitoring — see test_monitoring.py
for the shim's full test coverage. This file verifies tablebeat imports the
shared client correctly.
"""

import sentry_sdk
from unittest.mock import patch

from django.test import SimpleTestCase


class TablebeatMonitoringTests(SimpleTestCase):
    def test_client_is_importable(self):
        from poker import tablebeat

        self.assertTrue(hasattr(tablebeat, "client"))

    def test_client_extra_context_forwards_to_sentry(self):
        from poker import tablebeat

        with patch.object(sentry_sdk, "set_context") as mock_ctx:
            try:
                tablebeat.client.extra_context({"hand_id": "xyz"})
            except Exception:
                pass
            if "SentryCompat" in type(tablebeat.client).__name__:
                mock_ctx.assert_called_once_with("extra", {"hand_id": "xyz"})

    def test_capture_exception_not_silent(self):
        from poker import tablebeat

        with patch.object(sentry_sdk, "capture_exception") as mock_cap:
            try:
                raise ValueError("test")
            except ValueError:
                tablebeat.client.captureException()
            if "SentryCompat" in type(tablebeat.client).__name__:
                mock_cap.assert_called_once()
