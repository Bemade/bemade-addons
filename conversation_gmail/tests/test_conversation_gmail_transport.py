# Acceptance criteria (task #3965, conversation_gmail):
#   Blocking issue #1 (OAuth-connected inbox browsing): a Gmail account's
#     endpoints come from the provider itself (_email_connection_params,
#     never a stored host field anyone has to fill in) and `login` is
#     derived from Google's userinfo response rather than typed; the
#     transport authenticates with a mocked XOAUTH2 token from
#     google.gmail.mixin (never a stored password); an IMAP auth failure
#     triggers exactly one token-refresh-then-retry.
#   Blocking issue #3 (per-account OAuth credential override): an
#     account-level Client ID/Secret takes priority over the
#     instance-wide config; either alone still falls back correctly
#     (Workspace org sharing global credentials + a user on a personal
#     Gmail account with their own credentials, on the same instance).
#   Staging-review fix (2026-08-13, carried forward): "Connect to Gmail"
#     redirects an admin to General Settings when no credentials --
#     neither account-level nor instance-wide -- are configured, while
#     leaving the mixin's own AccessError for non-admins untouched.

import imaplib
from unittest.mock import patch

from odoo.exceptions import AccessError, RedirectWarning, UserError
from odoo.fields import Command
from odoo.tests import TransactionCase


class TestConversationGmailConnectionParams(TransactionCase):
    """Task #3965: Gmail's endpoints come from Gmail, and no credential
    other than the OAuth token is ever handed to the connection layer.
    Guarded on `provider`, so this holds whether or not conversation_imap
    (which contributes host/password fields of its own for *its*
    transports) is installed alongside."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Gmail Params Transport",
                "provider": "gmail",
                "login": "durpro@gmail.com",
                "google_gmail_refresh_token": "fake-refresh-token",
            }
        )

    def test_endpoints_are_gmails_own(self):
        params = self.transport._email_connection_params()
        self.assertEqual(params["imap_host"], "imap.gmail.com")
        self.assertEqual(params["imap_port"], 993)
        self.assertEqual(params["smtp_host"], "smtp.gmail.com")
        self.assertEqual(params["smtp_port"], 587)

    def test_gmail_files_its_own_sent_copy(self):
        # Gmail saves anything sent through its SMTP into [Gmail]/Sent
        # Mail by itself, so the engine must not APPEND a second copy --
        # the user would see every reply twice.
        self.assertTrue(self.transport._email_provider_saves_sent_copy())

    def test_connection_params_never_carry_a_password(self):
        # A Gmail account authenticates with XOAUTH2 only; nothing may
        # hand a stored secret to the IMAP/SMTP login path for it.
        self.assertFalse(self.transport._email_connection_params()["password"])


class TestConversationGmailOAuth2(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Gmail Test Transport",
                "provider": "gmail",
                "browsable": True,
                "sendable": True,
                "login": "durpro@gmail.com",
                "google_gmail_refresh_token": "fake-refresh-token",
            }
        )

    def test_oauth_string_built_from_mixin_without_network_call(self):
        with patch.object(
            type(self.transport),
            "_generate_oauth2_string",
            return_value="user=durpro@gmail.com\1auth=Bearer fake-access-token\1\1",
            autospec=True,
        ) as mocked:
            auth_string = self.transport._imap_oauth_string()
        mocked.assert_called_once_with(
            self.transport, "durpro@gmail.com", "fake-refresh-token"
        )
        self.assertIn("Bearer fake-access-token", auth_string)

    def test_oauth_string_none_when_not_connected(self):
        # Not yet connected (no refresh token) -- the engine's own
        # "configure the IMAP host and login" guard takes over from here,
        # unchanged (blocking issue #1: leave that guard in place).
        disconnected = self.env["conversation.transport"].create(
            {"name": "Not Connected", "provider": "gmail", "login": "someone@gmail.com"}
        )
        self.assertIsNone(disconnected._imap_oauth_string())

    def test_oauth_string_requires_login_once_connected(self):
        connected_no_login = self.env["conversation.transport"].create(
            {
                "name": "Connected No Login",
                "provider": "gmail",
                "google_gmail_refresh_token": "fake-refresh-token",
            }
        )
        with self.assertRaises(UserError):
            connected_no_login._imap_oauth_string()

    def test_force_refresh_clears_cached_access_token_expiration(self):
        self.transport.google_gmail_access_token_expiration = 9999999999
        with patch.object(
            type(self.transport),
            "_generate_oauth2_string",
            return_value="user=durpro@gmail.com\1auth=Bearer refreshed\1\1",
            autospec=True,
        ):
            self.transport._imap_oauth_string(force_refresh=True)
        self.assertEqual(self.transport.google_gmail_access_token_expiration, 0)


class FakeGmailIMAP:
    """Records connect target + auth calls; simulates a first-attempt
    auth failure to exercise the token-refresh-then-retry path."""

    fail_once = False
    selected = None
    connect_args = []
    authenticate_calls = []

    def __init__(self, host, port, timeout=None):
        FakeGmailIMAP.connect_args.append((host, port))

    def authenticate(self, mechanism, callback):
        FakeGmailIMAP.authenticate_calls.append((mechanism, callback(b"")))
        if FakeGmailIMAP.fail_once and len(FakeGmailIMAP.authenticate_calls) == 1:
            raise imaplib.IMAP4.error("token expired")

    def select(self, mailbox):
        FakeGmailIMAP.selected = mailbox
        return "OK", [b"0"]

    def close(self):
        pass

    def logout(self):
        pass


class TestConversationGmailOAuthConnection(TransactionCase):
    """Blocking issue #1: XOAUTH2 string construction and the
    token-refresh-then-retry path, exercised through the real IMAP
    connection helper conversation_email_base provides (mocked
    imaplib)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Gmail Connection Transport",
                "provider": "gmail",
                "browsable": True,
                "login": "durpro@gmail.com",
                "google_gmail_refresh_token": "fake-refresh-token",
            }
        )

    def setUp(self):
        super().setUp()
        FakeGmailIMAP.fail_once = False
        FakeGmailIMAP.connect_args = []
        FakeGmailIMAP.authenticate_calls = []
        patcher = patch.object(
            type(self.transport), "_get_imap_client_class", return_value=FakeGmailIMAP
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        oauth_patcher = patch.object(
            type(self.transport),
            "_generate_oauth2_string",
            side_effect=lambda self_, user, refresh_token: (
                "user=%s\1auth=Bearer token\1\1" % user
            ),
            autospec=True,
        )
        oauth_patcher.start()
        self.addCleanup(oauth_patcher.stop)

    def test_connects_with_xoauth2_not_a_password(self):
        with self.transport._imap_connection():
            pass
        self.assertEqual(len(FakeGmailIMAP.authenticate_calls), 1)
        mechanism, sasl_response = FakeGmailIMAP.authenticate_calls[0]
        self.assertEqual(mechanism, "XOAUTH2")
        self.assertIn(b"Bearer token", sasl_response)

    def test_auth_failure_refreshes_token_and_retries_once(self):
        FakeGmailIMAP.fail_once = True
        with self.transport._imap_connection():
            pass
        self.assertEqual(len(FakeGmailIMAP.authenticate_calls), 2)
        # google_gmail_access_token_expiration was reset by the forced
        # refresh (see test_force_refresh_clears_cached_access_token_expiration
        # above for the unit-level assertion on that step in isolation).
        self.assertEqual(self.transport.google_gmail_access_token_expiration, 0)


class FakeGmailSMTP:
    """Records the AUTH XOAUTH2 command and the outgoing message instead
    of opening a real socket."""

    sent = []
    envelopes = []
    auth_commands = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port

    def starttls(self):
        pass

    def docmd(self, command, args=""):
        FakeGmailSMTP.auth_commands.append((command, args))
        return 235, b"Authentication successful"

    def send_message(self, message, to_addrs=None):
        FakeGmailSMTP.sent.append(message)
        FakeGmailSMTP.envelopes.append(to_addrs)

    def quit(self):
        pass


class TestConversationGmailSend(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Gmail Send Transport",
                "provider": "gmail",
                "sendable": True,
                "login": "durpro@gmail.com",
                "google_gmail_refresh_token": "fake-refresh-token",
            }
        )
        cls.conversation = cls.env["mail.conversation"].create(
            {"name": "Gmail Conversation", "primary_transport_id": cls.transport.id}
        )

    def setUp(self):
        super().setUp()
        FakeGmailSMTP.sent = []
        FakeGmailSMTP.envelopes = []
        FakeGmailSMTP.auth_commands = []
        smtp_patcher = patch.object(
            type(self.transport),
            "_get_smtp_client_class",
            return_value=FakeGmailSMTP,
        )
        smtp_patcher.start()
        self.addCleanup(smtp_patcher.stop)
        oauth_patcher = patch.object(
            type(self.transport),
            "_generate_oauth2_string",
            return_value="user=durpro@gmail.com\1auth=Bearer fake-access-token\1\1",
            autospec=True,
        )
        oauth_patcher.start()
        self.addCleanup(oauth_patcher.stop)

    def test_send_authenticates_with_xoauth2_not_a_password(self):
        message = self.conversation.action_reply(
            "<p>Reply via Gmail</p>", recipients=["someone@example.com"]
        )
        self.assertEqual(len(FakeGmailSMTP.sent), 1)
        self.assertEqual(len(FakeGmailSMTP.auth_commands), 1)
        command, args = FakeGmailSMTP.auth_commands[0]
        self.assertEqual(command, "AUTH")
        self.assertTrue(args.startswith("XOAUTH2 "))
        self.assertEqual(message.transport_id, self.transport)


class TestConversationGmailConnectDerivesLogin(TransactionCase):
    """Blocking issue #1: the user types neither a host nor a login. The
    hosts are the provider's own constants (see
    TestConversationGmailConnectionParams); the login is derived from
    Google's userinfo response, exercised here through the real
    OAuth-callback hook with the network calls (token exchange, userinfo)
    mocked."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Gmail Connect Transport", "provider": "gmail"}
        )

    def test_connect_derives_login_never_typed_by_user(self):
        class _Response:
            ok = True

            def json(self):
                return {
                    "refresh_token": "new-refresh-token",
                    "access_token": "new-access-token",
                    "expires_in": 3600,
                }

            def raise_for_status(self):
                pass

        class _UserinfoResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"email": "connected-user@gmail.com"}

        with (
            patch(
                "odoo.addons.conversation_gmail.models.conversation_transport."
                "requests.post",
                return_value=_Response(),
            ),
            patch(
                "odoo.addons.conversation_gmail.models.conversation_transport."
                "requests.get",
                return_value=_UserinfoResponse(),
            ),
        ):
            self.transport._fetch_gmail_refresh_token("fake-authorization-code")

        self.assertEqual(self.transport.login, "connected-user@gmail.com")
        # ...and the endpoints were never stored fields to begin with.
        params = self.transport._email_connection_params()
        self.assertEqual(params["imap_host"], "imap.gmail.com")
        self.assertEqual(params["smtp_host"], "smtp.gmail.com")

    def test_userinfo_failure_never_blocks_the_connect(self):
        class _Response:
            ok = True

            def json(self):
                return {
                    "refresh_token": "new-refresh-token",
                    "access_token": "new-access-token",
                    "expires_in": 3600,
                }

        with (
            patch(
                "odoo.addons.conversation_gmail.models.conversation_transport."
                "requests.post",
                return_value=_Response(),
            ),
            patch(
                "odoo.addons.conversation_gmail.models.conversation_transport."
                "requests.get",
                side_effect=OSError("network unreachable"),
            ),
        ):
            self.transport._fetch_gmail_refresh_token("fake-authorization-code")

        self.assertFalse(self.transport.login)


class TestConversationGmailCredentialFallback(TransactionCase):
    """Blocking issue #3: account-level Client ID/Secret overrides the
    instance-wide pair; either configured alone still resolves."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Credential Fallback Transport", "provider": "gmail"}
        )

    def setUp(self):
        super().setUp()
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("google_gmail_client_id", "global-client-id")
        config.set_param("google_gmail_client_secret", "global-client-secret")

    def test_falls_back_to_global_when_account_level_unset(self):
        client_id, client_secret = self.transport._get_gmail_client_credentials()
        self.assertEqual(client_id, "global-client-id")
        self.assertEqual(client_secret, "global-client-secret")

    def test_account_level_overrides_global(self):
        self.transport.write(
            {"client_id": "account-client-id", "client_secret": "account-secret"}
        )
        client_id, client_secret = self.transport._get_gmail_client_credentials()
        self.assertEqual(client_id, "account-client-id")
        self.assertEqual(client_secret, "account-secret")

    def test_mixed_deployment_each_account_resolved_independently(self):
        # A Workspace org (global credentials) with one user who connected
        # their own personal Gmail address (their own credentials) --
        # both transports must resolve correctly side by side.
        personal = self.env["conversation.transport"].create(
            {
                "name": "Personal Gmail",
                "provider": "gmail",
                "client_id": "personal-client-id",
                "client_secret": "personal-secret",
            }
        )
        self.assertEqual(
            self.transport._get_gmail_client_credentials(),
            ("global-client-id", "global-client-secret"),
        )
        self.assertEqual(
            personal._get_gmail_client_credentials(),
            ("personal-client-id", "personal-secret"),
        )

    def test_google_gmail_uri_computed_from_account_level_credentials_alone(self):
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("google_gmail_client_id", "")
        config.set_param("google_gmail_client_secret", "")
        personal = self.env["conversation.transport"].create(
            {
                "name": "Personal Gmail URI",
                "provider": "gmail",
                "client_id": "personal-client-id",
                "client_secret": "personal-secret",
            }
        )
        self.assertTrue(personal.google_gmail_uri)
        self.assertIn("accounts.google.com", personal.google_gmail_uri)


class TestConversationGmailConnectRedirect(TransactionCase):
    """UAT gap (2026-08-13, task #3965): clicking "Connect to Gmail" with
    no credentials configured -- neither account-level nor
    instance-level -- must point the admin at where to configure it, not
    dead-end on a bare error."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Gmail Redirect Test",
                "provider": "gmail",
                "login": "durpro@gmail.com",
            }
        )
        cls.admin = cls.env["res.users"].create(
            {
                "name": "Test System Admin",
                "login": "test-gmail-oauth-admin@example.com",
                "groups_id": [Command.link(cls.env.ref("base.group_system").id)],
            }
        )
        cls.internal_user = cls.env["res.users"].create(
            {
                "name": "Test Internal User",
                "login": "test-gmail-oauth-user@example.com",
                "groups_id": [Command.link(cls.env.ref("base.group_user").id)],
            }
        )

    def setUp(self):
        super().setUp()
        # Each test runs in its own rolled-back savepoint (TransactionCase),
        # so clearing these here never leaks between tests.
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("google_gmail_client_id", "")
        config.set_param("google_gmail_client_secret", "")

    def test_admin_without_credentials_gets_redirected_to_settings(self):
        with self.assertRaises(RedirectWarning) as capture:
            self.transport.with_user(self.admin).open_google_gmail_uri()
        message, action_id, button_text, _context = capture.exception.args
        self.assertIn("General Settings", message)
        self.assertEqual(button_text, "Go to General Settings")
        self.assertEqual(
            action_id,
            self.env.ref("base_setup.action_general_configuration").id,
        )

    def test_admin_with_credentials_falls_through_to_mixin(self):
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("google_gmail_client_id", "fake-client-id")
        config.set_param("google_gmail_client_secret", "fake-client-secret")
        action = self.transport.with_user(self.admin).open_google_gmail_uri()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertIn("accounts.google.com", action["url"])

    def test_admin_with_only_client_id_set_still_gets_redirected(self):
        # The unset-check is an OR across the two config params -- a half-
        # configured instance (e.g. an admin who saved the Client ID but
        # not yet the Secret) must still be redirected, not fall through
        # to the mixin's opaque error.
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("google_gmail_client_id", "fake-client-id")
        with self.assertRaises(RedirectWarning) as capture:
            self.transport.with_user(self.admin).open_google_gmail_uri()
        message, action_id, button_text, _context = capture.exception.args
        self.assertIn("General Settings", message)
        self.assertEqual(button_text, "Go to General Settings")
        self.assertEqual(
            action_id,
            self.env.ref("base_setup.action_general_configuration").id,
        )

    def test_admin_with_only_client_secret_set_still_gets_redirected(self):
        # Same OR boundary, other side: Secret present but Client ID
        # missing must also redirect rather than fall through.
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("google_gmail_client_secret", "fake-client-secret")
        with self.assertRaises(RedirectWarning) as capture:
            self.transport.with_user(self.admin).open_google_gmail_uri()
        message, _action_id, button_text, _context = capture.exception.args
        self.assertIn("General Settings", message)
        self.assertEqual(button_text, "Go to General Settings")

    def test_admin_with_only_account_level_credentials_not_redirected(self):
        # Blocking issue #3: an account-level Client ID/Secret is enough
        # on its own -- the instance-wide config stays empty (a personal
        # Gmail account, no Workspace org involved).
        self.transport.write(
            {"client_id": "account-client-id", "client_secret": "account-secret"}
        )
        action = self.transport.with_user(self.admin).open_google_gmail_uri()
        self.assertEqual(action["type"], "ir.actions.act_url")

    def test_non_admin_keeps_original_access_error(self):
        with self.assertRaises(AccessError):
            self.transport.with_user(self.internal_user).open_google_gmail_uri()
