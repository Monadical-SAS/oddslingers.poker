"""
Monitoring shim — provides a raven-compatible client interface backed by sentry_sdk.

Usage:
    from oddslingers.monitoring import client
    client.extra_context({"key": "value"})
    client.captureException()
"""

try:
    from raven.contrib.django.raven_compat.models import client
except ImportError:
    try:
        import sentry_sdk
    except ImportError:
        import logging as _logging

        _logging.getLogger("oddslingers.monitoring").warning(
            "Neither raven nor sentry_sdk is installed — exceptions will not be reported."
        )
        sentry_sdk = None  # type: ignore[assignment]

    class _SentryCompat:  # type: ignore[misc]
        """Shim matching the raven client API, forwarding to sentry_sdk."""

        def extra_context(self, data: dict, *a, **kw):
            if sentry_sdk is not None:
                sentry_sdk.set_context("extra", data)

        def captureException(self, *a, **kw):
            if sentry_sdk is not None:
                # Forward explicit exception arg to match raven's positional API.
                # If no arg, capture_exception() uses sys.exc_info() from caller context.
                sentry_sdk.capture_exception(a[0] if a else None)

    client = _SentryCompat()
