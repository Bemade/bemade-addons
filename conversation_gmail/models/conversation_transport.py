import json
import logging

import requests
from werkzeug.urls import url_encode, url_join

from odoo import api, fields, models
from odoo.exceptions import RedirectWarning, UserError

_logger = logging.getLogger(__name__)

# Gmail's IMAP/SMTP endpoints are fixed -- unlike conversation_imap, there
# is no host/port to configure. Populated onto the shared
# conversation_imap fields (imap_host/imap_port/smtp_host/smtp_port) the
# moment an account connects -- see _fetch_gmail_refresh_token below --
# rather than derived on every connection, so conversation_imap's
# _imap_connection/_smtp_connection guard (unchanged) just works.
GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587

# Matches google_gmail_mixin's own GMAIL_TOKEN_REQUEST_TIMEOUT (not
# imported from it -- an internal constant of a different module, not a
# published API of google_gmail).
GMAIL_TOKEN_REQUEST_TIMEOUT = 5


class ConversationTransport(models.Model):
    """Gmail provider: registers itself as the ``gmail`` option on the
    shared ``provider`` Selection, then supplies exactly the two things
    that differ between a manually-configured IMAP account and a
    Gmail-OAuth one:

    1. **Credentials** -- ``google.gmail.mixin``'s OAuth2 token dance,
       reused as-is (no stored password, ever), with an account-level
       Client ID/Secret override on top of the mixin's instance-global
       config (task #3965, AC4 / blocking issue #3): one Gmail provider
       serves both a Google Workspace tenant (global credentials) and a
       user's personal Gmail account (their own credentials), resolved
       per-record so a mixed deployment works without special-casing.
    2. **The connection layer** ``conversation_email_base``'s single
       browse/fetch/normalize/send implementation asks a provider for:
       ``_email_connection_params()`` (Gmail's fixed endpoints, and no
       password ever) and ``_imap_oauth_string()`` (XOAUTH2 instead of a
       password login). Browse, search, fetch, normalize, match, send and
       push-subscribe are all inherited from the engine unchanged --
       Gmail is IMAP under the hood, so there is exactly one
       implementation of each, not a second copy that can drift out of
       sync or silently clobber the other's method (the root cause of the
       original "Configure the IMAP host and login" crash on a connected
       Gmail account: two modules independently overriding the same
       method names on the same model, with whichever loaded last winning
       for every transport, Gmail included).

    ``conversation_imap`` is deliberately **not** a dependency: a
    Gmail-only deployment has no reason to install generic IMAP/SMTP
    credential support. Both providers sit on the shared engine as
    siblings, and every override here is guarded on ``provider`` so the
    two never shadow each other when both happen to be installed.
    """

    _name = "conversation.transport"
    _inherit = ["conversation.transport", "google.gmail.mixin"]

    # Gmail needs the `email` scope alongside its own mail scope so the
    # userinfo endpoint (see _gmail_fetch_userinfo_email) will answer for
    # the token this consent produces -- deriving `login` from the
    # authenticated address rather than asking the user to type it
    # (blocking issue #1).
    _SERVICE_SCOPE = (
        "https://mail.google.com/ https://www.googleapis.com/auth/userinfo.email"
    )

    provider = fields.Selection(
        selection_add=[("gmail", "Gmail")],
        ondelete={"gmail": "cascade"},
        default="gmail",
    )
    client_id = fields.Char(
        string="Gmail Client ID",
        help="Override the instance-wide Google OAuth Client ID for this "
        "account only. Leave blank to use the one configured under "
        "Settings > General Settings > Emails > 'Use a Gmail Server' "
        "(the common case for a Google Workspace org sharing one OAuth "
        "app). Set this when connecting a personal Gmail account with "
        "its own Google Cloud OAuth client instead.",
    )
    client_secret = fields.Char(
        string="Gmail Client Secret",
        groups="base.group_system",
        help="Paired with Client ID above; leave both blank to use the "
        "instance-wide credentials. Treated as a credential, like the "
        "OAuth tokens below: only an administrator can read or edit it.",
    )

    # ------------------------------------------------------------
    # Connect-to-Gmail entrypoint -- wraps google.gmail.mixin's
    # open_google_gmail_uri() (only on OUR OWN conversation.transport
    # model; ir.mail_server/fetchmail.server, the mixin's other
    # consumers, are completely untouched) to fix a real UX dead end:
    # when neither this account's own Client ID/Secret nor the
    # instance-level pair (Settings > General Settings > Emails > Custom
    # Email Servers > Use a Gmail Server) is configured, the mixin's own
    # open_google_gmail_uri() just raises a bare UserError("Please
    # configure your Gmail credentials.") with no indication of where
    # that is. Detect that case up front and redirect straight to
    # General Settings with an actionable message instead.
    # ------------------------------------------------------------

    def open_google_gmail_uri(self):
        self.ensure_one()
        # Only pre-empt with the friendlier redirect for users who could
        # actually act on it -- everyone else keeps the mixin's own
        # AccessError, unchanged, via super() below.
        if self.env.user.has_group("base.group_system") and not self.google_gmail_uri:
            client_id, client_secret = self._get_gmail_client_credentials()
            if not client_id or not client_secret:
                settings_action = self.env.ref(
                    "base_setup.action_general_configuration"
                )
                raise RedirectWarning(
                    self.env._(
                        "Gmail OAuth is not set up for %(transport)s yet: "
                        "no Google Client ID/Secret is configured, either "
                        "on this account or instance-wide. Either enter a "
                        "Client ID/Secret on this account (for a personal "
                        "Gmail account), or ask an administrator to go to "
                        "Settings, then General Settings, then under "
                        "Emails enable 'Custom Email Servers', then fill "
                        "in the Gmail Client ID and Client Secret under "
                        "'Use a Gmail Server' and save. Come back here "
                        "afterwards and click 'Connect to Gmail' again.",
                        transport=self.display_name,
                    ),
                    settings_action.id,
                    self.env._("Go to General Settings"),
                )
                # else: google_gmail_uri is falsy for some other reason
                # (e.g. web.base.url misconfigured) -- fall through to the
                # mixin's own error rather than mask it as a credentials
                # issue.
        return super().open_google_gmail_uri()

    def _get_gmail_client_credentials(self):
        """Credential fallback chain (task #3965, AC4 / blocking issue
        #3): this account's own Client ID/Secret when set, else the
        instance-wide pair. Resolved per-record so a Google Workspace org
        (global credentials, the common case) and an individual user's
        personal Gmail account (their own credentials) can coexist on the
        same instance without a second provider."""
        self.ensure_one()
        config = self.env["ir.config_parameter"].sudo()
        client_id = self.client_id or config.get_param("google_gmail_client_id")
        client_secret = self.client_secret or config.get_param(
            "google_gmail_client_secret"
        )
        return client_id, client_secret

    @api.depends("google_gmail_authorization_code", "client_id", "client_secret")
    def _compute_gmail_uri(self):
        """Overrides google.gmail.mixin's own compute (registered only on
        our model -- ir.mail_server/fetchmail.server are untouched) to
        resolve the Client ID/Secret per-record through
        _get_gmail_client_credentials() instead of purely instance-global
        config, so the consent URL is built with whichever credentials
        this specific account will actually authenticate with."""
        base_url = self.get_base_url()
        redirect_uri = url_join(base_url, "/google_gmail/confirm")
        for record in self:
            client_id, client_secret = record._get_gmail_client_credentials()
            if not client_id or not client_secret:
                record.google_gmail_uri = False
                continue
            record.google_gmail_uri = (
                "https://accounts.google.com/o/oauth2/v2/auth?%s"
                % url_encode(
                    {
                        "client_id": client_id,
                        "redirect_uri": redirect_uri,
                        "response_type": "code",
                        "scope": record._SERVICE_SCOPE,
                        # access_type and prompt needed to get a refresh token
                        "access_type": "offline",
                        "prompt": "consent",
                        "state": json.dumps(
                            {
                                "model": record._name,
                                "id": record.id or False,
                                "csrf_token": (
                                    record._get_gmail_csrf_token()
                                    if record.id
                                    else False
                                ),
                            }
                        ),
                    }
                )
            )

    def _fetch_gmail_token(self, grant_type, **values):
        """Overrides google.gmail.mixin's own token-exchange call
        (registered only on our model) to authenticate with the
        per-record credential fallback instead of purely instance-global
        config -- otherwise a personal Gmail account's own Client
        ID/Secret would never actually be used, only its presence checked
        by _compute_gmail_uri above."""
        self.ensure_one()
        client_id, client_secret = self._get_gmail_client_credentials()
        base_url = self.get_base_url()
        redirect_uri = url_join(base_url, "/google_gmail/confirm")
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": grant_type,
                "redirect_uri": redirect_uri,
                **values,
            },
            timeout=GMAIL_TOKEN_REQUEST_TIMEOUT,
        )
        if not response.ok:
            raise UserError(
                self.env._("An error occurred when fetching the access token.")
            )
        return response.json()

    def _fetch_gmail_refresh_token(self, authorization_code):
        """After the mixin exchanges the authorization code for tokens,
        record the connected account's address so the engine has a login
        to authenticate as. The user never types a host -- Gmail's
        endpoints are constants supplied by
        ``_email_connection_params()`` below, not fields anyone fills in
        -- and never types the login either: it comes from Google's own
        userinfo response for the token this consent just produced."""
        self.ensure_one()
        refresh_token, access_token, expiration = super()._fetch_gmail_refresh_token(
            authorization_code
        )
        email_address = self._gmail_fetch_userinfo_email(access_token)
        if email_address:
            self.write({"login": email_address})
        return refresh_token, access_token, expiration

    def _gmail_fetch_userinfo_email(self, access_token):
        """The connected account's own address, from Google's userinfo
        endpoint (authenticated with the access token this same consent
        just produced) -- never typed by the user. Never raises: a
        userinfo hiccup shouldn't block the OAuth connect itself, it just
        means ``login`` stays whatever it was (typically blank, which
        surfaces as the engine's existing "configure the IMAP host and
        login" guard on the next browse -- a clear, actionable message,
        not a silent bad state)."""
        try:
            response = requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": "Bearer %s" % access_token},
                timeout=GMAIL_TOKEN_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            return response.json().get("email") or None
        except Exception:  # noqa: BLE001 - see docstring
            _logger.warning(
                "Gmail: could not fetch userinfo email for %s", self, exc_info=True
            )
            return None

    # ------------------------------------------------------------
    # The two hooks conversation_email_base's shared browse/fetch/
    # normalize/send implementation needs from a provider. Everything
    # else (_browse, _search_remote, _fetch, _normalize, _match_inbound,
    # _send, _subscribe_push, connection helpers) is inherited unchanged.
    # Both are guarded on `provider`: another provider installed
    # alongside must keep its own connection layer, whatever order Odoo
    # happens to load the two modules in.
    # ------------------------------------------------------------

    def _email_providers(self):
        return super()._email_providers() + ["gmail"]

    def _email_provider_saves_sent_copy(self):
        """Gmail files a copy of anything sent through its SMTP into
        [Gmail]/Sent Mail by itself, so the engine must not APPEND a
        second one -- the user would see every reply twice."""
        if self.provider != "gmail":
            return super()._email_provider_saves_sent_copy()
        return True

    def _email_connection_params(self):
        if self.provider != "gmail":
            return super()._email_connection_params()
        # Fixed endpoints, and no password at all: authentication is
        # XOAUTH2 via _imap_oauth_string below. Nothing here is a stored
        # field, so there is no host for a Gmail account to be missing.
        return {
            "imap_host": GMAIL_IMAP_HOST,
            "imap_port": GMAIL_IMAP_PORT,
            "imap_ssl": True,
            "smtp_host": GMAIL_SMTP_HOST,
            "smtp_port": GMAIL_SMTP_PORT,
            "smtp_starttls": True,
            "password": None,
        }

    def _imap_oauth_string(self, force_refresh=False):
        self.ensure_one()
        if self.provider != "gmail":
            return super()._imap_oauth_string(force_refresh=force_refresh)
        if not self.google_gmail_refresh_token:
            # Not (yet) connected via Gmail OAuth -- the engine's generic
            # guard ("configure the IMAP host and login") takes over,
            # since login is still blank at this point (see
            # _fetch_gmail_refresh_token above).
            return None
        if not self.login:
            raise UserError(
                self.env._(
                    "%(transport)s is connected to Gmail but has no login "
                    "address on file; reconnect the account.",
                    transport=self.display_name,
                )
            )
        if force_refresh:
            # Discard any cached access token so google.gmail.mixin's own
            # _generate_oauth2_string() below re-fetches one -- used when
            # an IMAP/SMTP auth attempt failed even though our own expiry
            # check thought the cached token was still good (e.g. revoked
            # or rotated out of band).
            self.google_gmail_access_token_expiration = 0
        return self._generate_oauth2_string(self.login, self.google_gmail_refresh_token)
