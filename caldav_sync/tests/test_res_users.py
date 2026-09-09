import logging
from unittest.mock import MagicMock, patch

import caldav

from odoo.tests import TransactionCase

from .common import CaldavTestCommon

_logger = logging.getLogger(__name__)


class TestUsers(TransactionCase, CaldavTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_caldav_enabled_false_without_url(self):
        # Create user with no CalDAV credentials
        user = self._generate_user("test")
        self.assertFalse(user.is_caldav_enabled)

    def test_caldav_enabled_false_without_credentials(self):
        """Test that is_caldav_enabled is False when any required field is missing."""
        # Test with missing URL - has username and password only
        user1 = self._generate_user(
            "test1", caldav_username="user1", caldav_password="pass1"
        )
        self.assertFalse(user1.is_caldav_enabled)

        # Test with missing username - has password and URL only
        user2 = self._generate_user(
            "test2", caldav_password="pass2", caldav_url="https://example.com"
        )
        self.assertFalse(user2.is_caldav_enabled)

        # Test with missing password - has username and URL only
        user3 = self._generate_user(
            "test3", caldav_username="user3", caldav_url="https://example.com"
        )
        self.assertFalse(user3.is_caldav_enabled)

    @patch("caldav.DAVClient")
    def test_caldav_enabled_success(self, MockDAVClient):
        """Test that is_caldav_enabled is True when connection succeeds."""
        # Create user with name 'test' and set CalDAV credentials
        user = self._generate_user(
            "test",
            caldav_username="user",
            caldav_password="pass",
            caldav_url="https://example.com/abc123",
        )

        # Mock successful connection
        mock_client = MockDAVClient.return_value
        mock_principal = MagicMock()
        mock_client.principal.return_value = mock_principal

        # Compute should succeed and set is_caldav_enabled to True
        user._compute_is_caldav_enabled()
        self.assertTrue(user.is_caldav_enabled)

    @patch("caldav.DAVClient")
    def test_caldav_enabled_connection_fails(self, MockDAVClient):
        """Test that is_caldav_enabled is False when connection fails."""
        user = self._generate_user(
            "test",
            caldav_username="user",
            caldav_password="pass",
            caldav_url="https://example.com/abc123",
        )

        # Mock failed connection
        mock_client = MockDAVClient.return_value
        mock_client.principal.side_effect = caldav.error.AuthorizationError(
            "Invalid credentials"
        )

        # Should handle the error gracefully and set is_caldav_enabled to False
        with self.assertLogs("odoo.addons.caldav_sync.models.res_users", "ERROR"):
            user._compute_is_caldav_enabled()
        self.assertFalse(user.is_caldav_enabled)
