import base64
import email
import email.policy
import imaplib
import logging
import re
import smtplib
import time
from contextlib import contextmanager
from email.message import EmailMessage
from email.utils import make_msgid

from odoo import fields, models
from odoo.addons.conversation_base.tools import mime
from odoo.exceptions import UserError
from odoo.tools.lru import LRU
from odoo.tools.mail import html2plaintext

_logger = logging.getLogger(__name__)

# Per-process, per-(transport, uid) envelope cache. Deliberately module-level
# (not per-record/per-request): the point is to avoid re-parsing the same
# message twice within a short span of page views, without ever holding an
# IMAP/SMTP socket open between requests -- the cache stores parsed dicts
# only, never a connection.
_ENVELOPE_CACHE = LRU(512)

DEFAULT_PAGE_SIZE = 25

# The UID in a FETCH response line, e.g. b'12 (UID 227398 BODY[...] {345}'.
_UID_RESPONSE_RE = re.compile(rb"UID\s+(\d+)")

# Socket timeout for every IMAP/SMTP connection, in seconds. imaplib and
# smtplib default to no timeout at all, which means a mail server that
# stops answering holds an Odoo worker until the request watchdog fires --
# `limit_time_real` is commonly 20 minutes, and a browse or a send holds a
# worker for the whole of it. With N workers, N such requests take the
# instance down, health checks included, and the container gets killed by
# its liveness probe.
#
# The ceiling that matters is the liveness probe's budget (period x
# failureThreshold, typically ~45s): if every worker can be stuck for
# longer than that at once, the instance dies rather than degrades. 30s
# keeps a total stall inside that budget while leaving room for a slow
# FETCH of a large message.
DEFAULT_SOCKET_TIMEOUT = 30


class ConversationTransport(models.Model):
    """The *one* IMAP/SMTP browse/fetch/normalize/match/send implementation,
    shared by every email-speaking provider (``conversation_imap``,
    ``conversation_gmail``, a future ``conversation_outlook``, ...). Only
    the connection layer differs between them -- endpoints and
    authentication -- so that is all a provider module supplies:

    * ``_email_providers()`` -- register the provider's ``provider`` code,
      so the engine knows this transport is one of its own;
    * ``_email_connection_params()`` -- the IMAP/SMTP endpoints and the
      password (if any) for that provider;
    * ``_imap_oauth_string()`` -- optional; return a SASL XOAUTH2 string to
      authenticate via OAuth instead of ``login``/``password``.

    **Dispatch is on the ``provider`` value, never on module load order.**
    Two provider modules installed side by side both extend
    ``conversation.transport``, so whichever module Odoo happens to load
    last would otherwise silently shadow the other's overrides (which is
    exactly how a Gmail transport ended up being asked for a generic
    ``imap_host`` it has no reason to carry). Every provider override
    therefore early-returns ``super()`` when ``self.provider`` is not its
    own -- the ``payment.provider`` pattern -- and the engine's own
    overrides likewise defer to ``super()`` for a non-email transport, so a
    non-email provider (SMS, WhatsApp, ...) still gets
    ``conversation_base``'s abstract hooks untouched.
    """

    _inherit = "conversation.transport"

    imap_folder = fields.Char(string="IMAP Folder", default="INBOX")
    imap_sent_folder = fields.Char(
        string="Sent Folder",
        default="Sent",
        help="Folder an outgoing message is APPENDed to after it is sent, "
        "so a reply sent from Odoo also appears in the account's own Sent "
        "mail. Leave blank to skip. Ignored for providers that save sent "
        "mail themselves (Gmail does; a generic IMAP/SMTP account does "
        "not, and without this an unfiled reply would exist nowhere at "
        "all).",
    )

    # ------------------------------------------------------------
    # Provider registration + dispatch
    # ------------------------------------------------------------

    def _email_providers(self):
        """Provider codes served by this IMAP/SMTP engine. Each provider
        module appends its own (``super()._email_providers() + ["imap"]``);
        this module implements no provider itself."""
        return []

    def _is_email_transport(self):
        """Whether the engine below owns this record, i.e. whether its
        ``provider`` is one an installed email provider module
        registered."""
        self.ensure_one()
        return self.provider in self._email_providers()

    def _email_provider_saves_sent_copy(self):
        """Whether the provider files a copy of outgoing mail in its own
        Sent folder without being asked. Gmail does this for anything sent
        through its SMTP, so APPENDing would show the message twice; a
        generic IMAP/SMTP account does not. Overridden per provider,
        guarded on ``provider`` like the rest."""
        self.ensure_one()
        return False

    def _email_connection_params(self):
        """Endpoints + credentials for this transport's provider, as a
        dict: ``imap_host``, ``imap_port``, ``imap_ssl``, ``smtp_host``,
        ``smtp_port``, ``smtp_starttls``, ``password``. Overridden by each
        provider module, guarded on its own ``provider`` value.

        ``login`` is not part of this: it lives on ``conversation.transport``
        itself and is the same field for every provider.
        """
        self.ensure_one()
        raise NotImplementedError(
            "%s registered provider %r on the email engine but implements "
            "no _email_connection_params for it."
            % (self._name, self.provider)
        )

    # ------------------------------------------------------------
    # Connection helpers -- short-lived, connection-per-call. Never stored
    # on self / never held across two separate hook invocations, so an
    # inbox page view or a send never keeps a socket open between requests.
    # The client classes are looked up through small factory methods so
    # tests can substitute fakes without patching the stdlib.
    # ------------------------------------------------------------

    def _get_imap_client_class(self, use_ssl=True):
        return imaplib.IMAP4_SSL if use_ssl else imaplib.IMAP4

    def _get_smtp_client_class(self):
        return smtplib.SMTP

    def _email_socket_timeout(self):
        """Seconds before an unresponsive mail server gives a worker back.
        See DEFAULT_SOCKET_TIMEOUT: raise it for a provider that is
        legitimately slow, but keep it under the deployment's liveness
        probe budget, or a stall becomes a restart."""
        self.ensure_one()
        return DEFAULT_SOCKET_TIMEOUT

    def _imap_oauth_string(self, force_refresh=False):
        """Hook: return a SASL XOAUTH2 string to authenticate this
        transport via OAuth, or ``None`` to fall back to a plain
        ``login``/``password`` login. Generic IMAP has no OAuth of its
        own, so the default is ``None``; OAuth-capable providers
        (``conversation_gmail``, a future ``conversation_outlook``, ...)
        override this and do **not** need to touch ``_imap_connection``/
        ``_smtp_connection`` themselves.

        ``force_refresh=True`` asks the provider to discard any cached
        access token and fetch a fresh one -- used for the
        retry-once-on-auth-failure path below, for the case a token goes
        stale between the provider's own pre-flight expiry check and the
        actual IMAP/SMTP round trip (e.g. revoked/rotated out of band).
        """
        self.ensure_one()
        return None

    @contextmanager
    def _imap_connection(self):
        self.ensure_one()
        params = self._email_connection_params()
        if not params.get("imap_host") or not self.login:
            raise UserError(
                self.env._(
                    "Configure the IMAP host and login before browsing "
                    "%(transport)s.",
                    transport=self.display_name,
                )
            )
        # pylint: disable=assignment-from-none
        # _imap_oauth_string is a soft/optional hook (unlike the
        # abstract, NotImplementedError-raising hooks on
        # conversation.transport): the base always returns None by
        # design, an OAuth-capable provider module (conversation_gmail,
        # ...) overrides it -- pylint only sees this file's own
        # definition, not the cross-module override.
        oauth_string = self._imap_oauth_string()
        client_cls = self._get_imap_client_class(use_ssl=params.get("imap_ssl", True))
        connection = client_cls(
            params["imap_host"],
            params.get("imap_port") or 993,
            timeout=self._email_socket_timeout(),
        )
        try:
            if oauth_string:
                self._imap_xoauth2_login(connection, oauth_string)
            else:
                connection.login(self.login, params.get("password") or "")
            # Stash the EXISTS count the SELECT already returned. SELECT
            # is the expensive command on a large mailbox (seconds on a
            # Gmail folder of any size), and paging needs that count --
            # so without this it gets asked for a second time per browse,
            # doubling the dominant cost to learn a number we were just
            # told.
            connection.conversation_exists = self._imap_select(connection)
            yield connection
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                _logger.debug("IMAP close failed (ignored)", exc_info=True)
            try:
                connection.logout()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                _logger.debug("IMAP logout failed (ignored)", exc_info=True)

    def _imap_xoauth2_login(self, connection, oauth_string):
        """XOAUTH2 SASL authenticate; on an auth failure, ask the provider
        for a freshly-refreshed token and retry exactly once."""
        try:
            connection.authenticate("XOAUTH2", lambda _resp: oauth_string.encode())
        except imaplib.IMAP4.error:
            refreshed = self._imap_oauth_string(  # pylint: disable=assignment-from-none
                force_refresh=True
            )
            if not refreshed:
                raise
            connection.authenticate("XOAUTH2", lambda _resp: refreshed.encode())

    @contextmanager
    def _smtp_connection(self):
        self.ensure_one()
        params = self._email_connection_params()
        if not params.get("smtp_host") or not self.login:
            raise UserError(
                self.env._(
                    "Configure the SMTP host and login before sending from "
                    "%(transport)s.",
                    transport=self.display_name,
                )
            )
        oauth_string = self._imap_oauth_string()  # pylint: disable=assignment-from-none
        client_cls = self._get_smtp_client_class()
        connection = client_cls(
            params["smtp_host"],
            params.get("smtp_port") or 587,
            timeout=self._email_socket_timeout(),
        )
        try:
            if params.get("smtp_starttls", True):
                connection.starttls()
            if oauth_string:
                self._smtp_xoauth2_login(connection, oauth_string)
            else:
                connection.login(self.login, params.get("password") or "")
            yield connection
        finally:
            try:
                connection.quit()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                _logger.debug("SMTP quit failed (ignored)", exc_info=True)

    def _smtp_xoauth2_login(self, connection, oauth_string):
        """SMTP has no built-in XOAUTH2 SASL helper (unlike imaplib), so
        this issues the raw ``AUTH XOAUTH2`` command directly; on failure,
        ask the provider for a freshly-refreshed token and retry once."""
        code, _response = connection.docmd(
            "AUTH", "XOAUTH2 " + base64.b64encode(oauth_string.encode()).decode()
        )
        if code != 235:
            refreshed = self._imap_oauth_string(  # pylint: disable=assignment-from-none
                force_refresh=True
            )
            if refreshed:
                code, _response = connection.docmd(
                    "AUTH",
                    "XOAUTH2 " + base64.b64encode(refreshed.encode()).decode(),
                )
        if code != 235:
            raise UserError(
                self.env._(
                    "SMTP XOAUTH2 authentication failed for %(transport)s.",
                    transport=self.display_name,
                )
            )

    def _imap_page_size(self):
        return DEFAULT_PAGE_SIZE

    def _imap_quote_mailbox(self, name):
        """A folder name as an IMAP mailbox argument, **quoted**. imaplib
        passes the name through verbatim, so an unquoted folder containing
        a space is parsed as two arguments and the command fails -- which
        is every one of Gmail's own special folders (``[Gmail]/Sent
        Mail``, ``[Gmail]/All Mail``, ...). The embedded quote/backslash
        strip keeps a hand-typed folder name from breaking out of the
        quoted string."""
        return '"%s"' % (name or "").replace("\\", "").replace('"', "")

    def _imap_mailbox(self):
        """The configured browse folder, quoted for IMAP."""
        self.ensure_one()
        return self._imap_quote_mailbox(self.imap_folder or "INBOX")

    def _imap_select(self, connection):
        """SELECT the configured mailbox; return how many messages it
        holds (the untagged EXISTS count, which is what ``select`` returns
        on success)."""
        self.ensure_one()
        typ, data = connection.select(self._imap_mailbox())
        if typ != "OK":
            raise UserError(
                self.env._(
                    "Could not open folder %(folder)s on %(transport)s.",
                    folder=self.imap_folder or "INBOX",
                    transport=self.display_name,
                )
            )
        try:
            return int(data[0])
        except (IndexError, TypeError, ValueError):
            return 0

    # ------------------------------------------------------------
    # conversation.transport hooks
    # ------------------------------------------------------------

    def _browse(self, query=None, page=1):
        self.ensure_one()
        if not self._is_email_transport():
            return super()._browse(query=query, page=page)
        page = max(page, 1)
        page_size = self._imap_page_size()
        with self._imap_connection() as connection:
            if query:
                page_uids, has_more = self._imap_query_page(
                    connection, query, page, page_size
                )
            else:
                page_uids, has_more = self._imap_sequence_page(
                    connection, page, page_size
                )
            items = self._imap_fetch_stubs(connection, page_uids)
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
        }

    def _imap_sequence_page(self, connection, page, page_size):
        """One page of UIDs, newest first, without ever asking the server
        for the whole mailbox.

        The obvious ``UID SEARCH ALL`` is unusable on a real mailbox: the
        server answers with *every* UID on a single line, and imaplib
        refuses to read a line past ``_MAXLINE`` (1 MB), which a mailbox
        of a few hundred thousand messages exceeds -- so opening the inbox
        failed outright, having transferred megabytes to display 25 rows.

        Sequence numbers are 1..EXISTS in mailbox order (oldest first), so
        the newest page is the top of that range, and searching within
        that range bounds the response to at most ``page_size`` UIDs. The
        subsequent FETCH still goes by UID, so nothing downstream changes.
        Sequence numbers do shift if mail arrives or is expunged between
        two page requests -- the same small race every IMAP client paging
        this way accepts, and the ingest-on-action design means nothing is
        persisted from a browse page anyway.
        """
        # The connection context manager already SELECTed and kept the
        # EXISTS count; reuse it. Re-SELECTing only to re-read that number
        # costs as much as the rest of the page put together. Fall back
        # for a caller that supplied its own connection.
        total = getattr(connection, "conversation_exists", None)
        if total is None:
            total = self._imap_select(connection)
        start = (page - 1) * page_size
        if start >= total:
            return [], False
        high = total - start
        low = max(1, high - page_size + 1)
        typ, data = connection.uid("search", None, "%d:%d" % (low, high))
        if typ != "OK":
            raise UserError(
                self.env._(
                    "IMAP search failed for %(transport)s.",
                    transport=self.display_name,
                )
            )
        uids = (data[0] or b"").split()
        uids.reverse()  # newest first
        return uids, low > 1

    def _imap_query_page(self, connection, query, page, page_size):
        """One page of UIDs matching an explicit search query. A query is
        the user's own narrowing, so it is issued as-is and paged in
        Python; a query broad enough to still overrun imaplib's line limit
        surfaces as an ask-for-something-narrower error rather than an
        opaque protocol failure."""
        try:
            typ, data = connection.uid("search", None, query)
        except imaplib.IMAP4.error as error:
            raise UserError(
                self.env._(
                    "The search returned too many results on "
                    "%(transport)s. Narrow it down (add a sender, a "
                    "subject or a date) and try again.",
                    transport=self.display_name,
                )
            ) from error
        if typ != "OK":
            raise UserError(
                self.env._(
                    "IMAP search failed for %(transport)s.",
                    transport=self.display_name,
                )
            )
        uids = (data[0] or b"").split()
        uids.reverse()  # newest first
        start = (page - 1) * page_size
        return uids[start : start + page_size], len(uids) > start + page_size

    def _search_remote(self, criteria):
        self.ensure_one()
        if not self._is_email_transport():
            return super()._search_remote(criteria)
        query = self._imap_build_search_query(criteria or {})
        return self._browse(query=query, page=1)

    def _imap_build_search_query(self, criteria):
        """Translate a light criteria dict (``subject``, ``from_``, ``to``,
        ``since``) into an IMAP SEARCH query string. Unrecognized/empty
        criteria fall back to ``ALL``."""
        parts = []
        if criteria.get("subject"):
            parts.append('SUBJECT "%s"' % criteria["subject"].replace('"', ""))
        if criteria.get("from_"):
            parts.append('FROM "%s"' % criteria["from_"].replace('"', ""))
        if criteria.get("to"):
            parts.append('TO "%s"' % criteria["to"].replace('"', ""))
        if criteria.get("since"):
            parts.append("SINCE %s" % criteria["since"])
        return " ".join(parts) if parts else "ALL"

    def _fetch(self, external_id):
        self.ensure_one()
        if not self._is_email_transport():
            return super()._fetch(external_id)
        cache_key = (self.id, external_id)
        cached = _ENVELOPE_CACHE.get(cache_key)
        if cached is not None:
            return cached
        uid = self._imap_uid_for_external_id(external_id)
        with self._imap_connection() as connection:
            typ, data = connection.uid("fetch", uid, "(RFC822)")
            if typ != "OK" or not data or data[0] is None:
                raise UserError(
                    self.env._(
                        "Could not fetch message %(external_id)s on "
                        "%(transport)s.",
                        external_id=external_id,
                        transport=self.display_name,
                    )
                )
            raw_bytes = data[0][1]
        raw = {"external_id": external_id, "rfc822": raw_bytes}
        _ENVELOPE_CACHE[cache_key] = raw
        return raw

    def _imap_uid_for_external_id(self, external_id):
        """A message's ``external_id`` on an IMAP-speaking provider *is*
        its IMAP UID (see ``_imap_fetch_stubs``/``_normalize``), so no extra
        round trip is needed to resolve one from the other."""
        return external_id.encode() if isinstance(external_id, str) else external_id

    def _imap_fetch_stubs(self, connection, uids):
        """Cheap per-message metadata for a whole browse page in **one**
        round trip: headers only, no body download (the body is fetched
        lazily via ``_fetch``/``fetch_envelope`` only when a human expands
        the item).

        One FETCH per message is what makes an inbox feel broken. IMAP is
        request/response over a single connection, so N messages cost N
        sequential round trips, and against Gmail each one runs into the
        seconds -- a 25-message page measured at 92s on a live account.
        A UID set costs one. The server may answer in any order, so the
        UID is read back out of each response line rather than assumed,
        and the caller's order is restored at the end.
        """
        self.ensure_one()
        wanted = [
            uid.decode() if isinstance(uid, bytes) else str(uid) for uid in uids
        ]
        stubs = {}
        missing = []
        for external_id in wanted:
            cached = _ENVELOPE_CACHE.get(("stub", self.id, external_id))
            if cached is not None:
                stubs[external_id] = cached
            else:
                missing.append(external_id)

        if missing:
            typ, data = connection.uid(
                "fetch",
                ",".join(missing),
                "(BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE MESSAGE-ID)])",
            )
            if typ != "OK":
                raise UserError(
                    self.env._(
                        "Could not read message headers on %(transport)s.",
                        transport=self.display_name,
                    )
                )
            for part in data or []:
                # imaplib yields (b'<seq> (UID <uid> BODY[...] {<n>}',
                # b'<headers>') for each message, interleaved with bare
                # b')' terminators -- skip anything that is not a pair.
                if not isinstance(part, (tuple, list)) or len(part) < 2:
                    continue
                match = _UID_RESPONSE_RE.search(part[0] or b"")
                if not match:
                    continue
                external_id = match.group(1).decode()
                stub = self._imap_parse_stub(external_id, part[1] or b"")
                _ENVELOPE_CACHE[("stub", self.id, external_id)] = stub
                stubs[external_id] = stub

        # Newest-first order comes from the caller, not from the server.
        return [stubs[key] for key in wanted if key in stubs]

    def _imap_parse_stub(self, external_id, header_bytes):
        """Raw RFC822 header block -> the canonical stub dict."""
        headers = email.message_from_bytes(header_bytes, policy=email.policy.default)
        return {
            "external_id": external_id,
            "subject": headers.get("Subject", ""),
            "email_from": mime.first_address(headers.get("From", "")),
            "to": mime.addresses(headers.get("To", "")),
            "cc": mime.addresses(headers.get("Cc", "")),
            "date": mime.parse_date(headers.get("Date")),
            "message_id": (headers.get("Message-Id") or "").strip(),
        }

    def _normalize(self, raw):
        self.ensure_one()
        if not self._is_email_transport():
            return super()._normalize(raw)
        message = email.message_from_bytes(
            raw["rfc822"], policy=email.policy.default
        )
        return {
            "external_id": raw.get("external_id"),
            "message_id": (message.get("Message-Id") or "").strip(),
            "subject": message.get("Subject", ""),
            "email_from": mime.first_address(message.get("From", "")),
            "to": mime.addresses(message.get("To", "")),
            "cc": mime.addresses(message.get("Cc", "")),
            "date": mime.parse_date(message.get("Date")),
            "body": mime.extract_body(message),
            "attachments": mime.extract_attachments(message),
            "in_reply_to": (message.get("In-Reply-To") or "").strip(),
            "references": (message.get("References") or "").strip(),
        }

    def _email_message_is_mine(self, message, conversation):
        """Did ``message`` travel over *this* transport?

        A quiet-captured inbound note carries a falsy ``transport_id`` by
        design (the notification-safety marker), so for those the
        conversation's ``primary_transport_id`` is what identifies the
        transport. Outbound messages recorded by ``_record_outbound`` do
        carry it. Shared by ``_match_inbound`` and
        ``_imap_reply_headers``; ``_find_captured`` applies the same rule
        from the conversation side.
        """
        self.ensure_one()
        if message.transport_id:
            return message.transport_id == self
        return conversation.primary_transport_id == self

    def _match_inbound(self, raw):
        """Within-transport correlation only: the existing
        ``mail.message`` whose thread this raw message continues, matched
        by its References/In-Reply-To against ``mail.message.message_id``.

        Two things this must NOT do, both of which made it match nothing
        at all:

        - Match against ``external_id``. On an email transport that holds
          the IMAP UID (a per-mailbox integer), never an RFC message-id,
          so comparing it to References/In-Reply-To could not succeed. The
          angle-bracketed id lives in ``message_id``. It is still
          ``external_id`` that marks a message as transport-borne, so it
          is required -- an ordinary internal note carries an
          Odoo-generated ``message_id`` no correspondent has ever seen.
        - Filter on ``transport_id = self.id`` in the query. Captured
          inbound notes leave that falsy on purpose, so the filter
          excluded precisely the messages worth correlating to.
        """
        self.ensure_one()
        if not self._is_email_transport():
            return super()._match_inbound(raw)
        message = email.message_from_bytes(
            raw["rfc822"], policy=email.policy.default
        )
        candidates = mime.correlation_candidates(message)
        if not candidates:
            return self.env["mail.message"]
        # Provenance cannot be expressed as a domain (it depends on the
        # conversation for transport-less notes), so filter in Python over
        # the message-id matches -- a set bounded by the correspondent's
        # own References header.
        matches = self.env["mail.message"].search(
            [
                ("model", "=", "mail.conversation"),
                ("message_id", "in", list(candidates)),
                ("external_id", "!=", False),
            ],
            order="id desc",
        )
        for candidate in matches:
            conversation = self.env["mail.conversation"].browse(candidate.res_id)
            if conversation.exists() and self._email_message_is_mine(
                candidate, conversation
            ):
                return candidate
        return self.env["mail.message"]

    def _send(self, conversation, message, recipients=None):
        """Send an already-posted ``mail.message``: a thin wrapper that
        derives plain values from the record and hands them to
        ``_send_raw``. The message's OWN Message-Id goes on the wire
        rather than a second minted one (what mail_mail does too), so the
        id a recipient quotes back in In-Reply-To is the one
        ``mail.message`` already stores."""
        self.ensure_one()
        if not self._is_email_transport():
            return super()._send(conversation, message, recipients=recipients)
        to_emails = recipients or self._imap_default_recipients(conversation)
        if not to_emails:
            raise UserError(
                self.env._(
                    "No recipient to send to on %(transport)s.",
                    transport=self.display_name,
                )
            )
        message_id = self._send_raw(
            subject=message.subject or conversation.name,
            body=message.body or "",
            to_emails=to_emails,
            in_reply_to=self._imap_reply_headers(conversation, message),
            attachments=self._email_attachment_payloads(message.attachment_ids),
            message_id=message.message_id,
        )
        return message_id.strip("<>")

    def _send_raw(
        self,
        subject,
        body,
        to_emails,
        cc=None,
        bcc=None,
        in_reply_to=None,
        attachments=None,
        message_id=None,
    ):
        """The send primitive -- see conversation.transport._send_raw.
        Persists nothing in Odoo: this is the path a personal-mailbox
        triage takes when the user chooses not to file the exchange into
        the shared hub."""
        self.ensure_one()
        if not self._is_email_transport():
            return super()._send_raw(
                subject,
                body,
                to_emails,
                cc=cc,
                bcc=bcc,
                in_reply_to=in_reply_to,
                attachments=attachments,
                message_id=message_id,
            )
        to_emails = [address for address in (to_emails or []) if address]
        cc = [address for address in (cc or []) if address]
        bcc = [address for address in (bcc or []) if address]
        if not (to_emails or cc or bcc):
            raise UserError(
                self.env._(
                    "No recipient to send to on %(transport)s.",
                    transport=self.display_name,
                )
            )
        outgoing = EmailMessage()
        outgoing["Subject"] = subject or ""
        outgoing["From"] = self.login
        if to_emails:
            outgoing["To"] = ", ".join(to_emails)
        if cc:
            outgoing["Cc"] = ", ".join(cc)
        # Bcc is deliberately NOT a header: it goes in the SMTP envelope
        # only (below), so no recipient can see who was blind-copied.
        native_message_id = message_id or make_msgid()
        outgoing["Message-Id"] = native_message_id
        if in_reply_to:
            outgoing["In-Reply-To"] = in_reply_to
            outgoing["References"] = in_reply_to
        prepared = self._email_prepare_body(body or "")
        # multipart/alternative: a text/plain part alongside the HTML.
        # An HTML-only message is treated as a spam signal by several
        # filters and is unreadable in a plaintext client.
        outgoing.set_content(html2plaintext(prepared) if prepared else "")
        outgoing.add_alternative(prepared, subtype="html")
        for attachment in attachments or []:
            maintype, _slash, subtype = (
                attachment.get("mimetype") or "application/octet-stream"
            ).partition("/")
            outgoing.add_attachment(
                attachment["content"],
                maintype=maintype,
                subtype=subtype or "octet-stream",
                filename=attachment.get("filename") or "attachment",
            )

        with self._smtp_connection() as connection:
            connection.send_message(outgoing, to_addrs=to_emails + cc + bcc)
        self._imap_append_to_sent(outgoing)
        return native_message_id

    def _email_attachment_payloads(self, attachments):
        """``ir.attachment`` recordset -> the plain dicts ``_send_raw``
        takes. Kept here so callers never have to know how the engine
        wants attachments shaped."""
        payloads = []
        for attachment in attachments or []:
            payloads.append(
                {
                    "filename": attachment.name,
                    "content": base64.b64decode(attachment.datas or b""),
                    "mimetype": attachment.mimetype,
                }
            )
        return payloads

    def _imap_append_to_sent(self, outgoing):
        """APPEND a just-sent message to the account's Sent folder, so it
        also shows up in the user's own mail client.

        Conditional on the provider: Gmail saves anything sent through its
        SMTP by itself, so APPENDing would duplicate it. A generic
        IMAP/SMTP account saves nothing -- without this an unfiled reply
        (the default, see the composer) would exist nowhere at all, having
        been sent but never persisted on either side.

        Never raises: the message is already delivered by this point, so
        a failure to file a copy is a warning, not a lost send.
        """
        self.ensure_one()
        if self._email_provider_saves_sent_copy() or not self.imap_sent_folder:
            return False
        try:
            with self._imap_connection() as connection:
                connection.append(
                    self._imap_quote_mailbox(self.imap_sent_folder),
                    "\\Seen",
                    imaplib.Time2Internaldate(time.time()),
                    outgoing.as_bytes(),
                )
        except Exception:  # noqa: BLE001 - see docstring
            _logger.warning(
                "Could not append the sent message to %s on %s",
                self.imap_sent_folder,
                self.display_name,
                exc_info=True,
            )
            return False
        return True

    def _email_prepare_body(self, body):
        """Make an Odoo-composed HTML body safe to read outside Odoo:
        rewrite root-relative links to absolute ones, exactly as
        ``mail_mail`` does before sending. Without it a link to an
        attachment or an inline image goes out as ``/web/content/...``,
        which resolves against the recipient's own mail client (``mail://
        vfolder/...`` in Thunderbird) and arrives dead."""
        self.ensure_one()
        if not body:
            return body
        return self.env["mail.render.mixin"]._replace_local_links(body)

    def _imap_default_recipients(self, conversation):
        participants = conversation.participant_ids.filtered(
            lambda p: p.role in ("to", "requester") and p.email_normalized
        )
        return [p.email_normalized for p in participants]

    def _imap_reply_headers(self, conversation, message):
        """The RFC822 Message-Id to thread an outbound reply against:
        the most recent message on this conversation that actually
        travelled over this transport.

        ``external_id`` is deliberately *not* that id. On an inbound
        capture it holds the IMAP UID (a per-mailbox integer like
        ``227398``), so using it produced an ``In-Reply-To: 227398`` that
        matches nothing in the recipient's client and threads nowhere;
        ``message_id`` is the real, angle-bracketed RFC id. It is still
        ``external_id`` that marks a message as having come over a
        transport at all, which is why it is required here -- an ordinary
        internal note also carries an Odoo-generated ``message_id``, but
        no correspondent has ever seen it.

        Provenance follows ``_find_captured``'s convention: a quiet-
        captured inbound note carries a falsy ``transport_id`` by design
        (the notification-safety marker), so for those the conversation's
        ``primary_transport_id`` is what identifies the transport.
        """
        previous = conversation.message_ids.filtered(
            lambda m: m.id != message.id
            and m.external_id
            and m.message_id
            and self._email_message_is_mine(m, conversation)
        ).sorted("id")
        return previous[-1:].message_id if previous else False

    def _subscribe_push(self):
        self.ensure_one()
        if not self._is_email_transport():
            return super()._subscribe_push()
        raise NotImplementedError(
            "The IMAP/SMTP engine is poll/browse-only; pushable stays False."
        )
