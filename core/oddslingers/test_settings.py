"""
Tests for security-sensitive settings invariants.
"""

from django.test import SimpleTestCase
from django.conf import settings


class SecureSettingsTests(SimpleTestCase):
    """Credentials that must never appear in logs or settings dumps."""

    def test_sentry_dsn_secret_is_secure(self):
        self.assertIn(
            "SENTRY_DSN_SECRET",
            settings.SECURE_SETTINGS,
            "SENTRY_DSN_SECRET must be in SECURE_SETTINGS to prevent "
            "exposure via settings inspection utilities and STATUS_LINE",
        )

    def test_sentry_dsn_key_is_secure(self):
        self.assertIn("SENTRY_DSN_KEY", settings.SECURE_SETTINGS)

    def test_secret_key_is_secure(self):
        self.assertIn("SECRET_KEY", settings.SECURE_SETTINGS)

    def test_postgres_password_is_secure(self):
        self.assertIn("POSTGRES_PASSWORD", settings.SECURE_SETTINGS)


class TrustedProxyCIDRsTests(SimpleTestCase):
    """TRUSTED_PROXY_CIDRS must be present and include private-network ranges."""

    def test_trusted_proxy_cidrs_defined(self):
        self.assertTrue(
            hasattr(settings, "TRUSTED_PROXY_CIDRS"),
            "TRUSTED_PROXY_CIDRS must be defined so X-Real-IP is only trusted "
            "from known proxy addresses",
        )

    def test_trusted_proxy_cidrs_is_list(self):
        self.assertIsInstance(settings.TRUSTED_PROXY_CIDRS, (list, tuple))

    def test_trusted_proxy_cidrs_not_empty(self):
        self.assertTrue(
            len(settings.TRUSTED_PROXY_CIDRS) > 0,
            "TRUSTED_PROXY_CIDRS must have at least one entry (e.g. 127.0.0.1/32)",
        )
