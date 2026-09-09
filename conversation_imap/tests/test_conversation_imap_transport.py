# Acceptance criteria (task #3965, conversation_imap):
#   Note (2026-08-14 refactor): the browse/fetch/normalize/match/send
#     implementation these tests exercise now lives in
#     conversation_email_base, shared with every other email provider.
#     They are kept here rather than moved because running them through a
#     real, fully-configured provider is what makes them meaningful -- the
#     engine has no provider of its own to connect with.
#   Test plan #1 (_normalize ETL): a fixture .eml normalizes to the
#     canonical dict; covers the non-obvious parses -- a multipart body
#     (HTML preferred) and a bare-email From with no partner. Also guards
#     the plaintext-body escaping fix (a plaintext body must never be
#     raw-interpolated into the HTML message body).
#   Test plan #2 (_match_inbound correlation): a raw whose
#     References/In-Reply-To matches an existing message's message_id
#     returns that conversation's message; an unknown raw returns falsy; a
#     match is never returned across a different transport. Covers both
#     message shapes -- outbound (transport_id set) and quiet-captured
#     inbound (transport_id falsy, provenance from the conversation) --
#     because the original tests only ever built the first and wrote an
#     RFC id into external_id, a state capture does not produce, which is
#     how the method shipped matching nothing at all.
#   Test plan #6 (outbound _send): a stub transport whose _send is
#     captured records the outbound mail.message with transport_id +
#     external_id, delivered to the explicit recipient list.
#   Test plan #9 (view smoke): Form on the imap-extended transport config
#     view builds (guards missing view fields).
#   Blocking issue #1 (2026-08-13 redo): _imap_connection authenticates
#     with XOAUTH2 instead of a password when a provider's
#     _imap_oauth_string hook returns one (conversation_gmail's is the
#     concrete case, exercised end to end in its own tests; this covers
#     the generic dispatch conversation_imap itself owns), and retries
#     exactly once -- with a freshly-refreshed token -- on an auth
#     failure. The base "configure the IMAP host and login" guard is
#     unchanged either way.
#   Blocking issue #1 (tester-added): _browse -- the IMAP UID SEARCH +
#     per-message header FETCH + pagination that browse_page actually
#     delegates to -- had no test anywhere exercising it end to end
#     (only the connection/auth layer and the base's dispatch-mocked
#     version were covered). Added here with a fake IMAP client that
#     implements uid("search"/"fetch"), covering newest-first ordering
#     and has_more/pagination, plus a browse_page smoke test that
#     confirms the RPC entry point reaches this real implementation.

import imaplib
from pathlib import Path
from unittest.mock import patch

from odoo.addons.conversation_email_base.models.conversation_transport import (
    _ENVELOPE_CACHE,
)
from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase

FIXTURES = Path(__file__).parent / "fixtures"


def _read_fixture(name):
    return (FIXTURES / name).read_bytes()


class TestConversationImapNormalize(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "IMAP Test Transport",
                "provider": "imap",
                "browsable": True,
                "searchable": True,
                "sendable": True,
                "login": "sales@example.com",
                "imap_host": "imap.example.com",
                "smtp_host": "smtp.example.com",
            }
        )

    def test_normalize_multipart_prefers_html_and_captures_references(self):
        raw = {"external_id": "42", "rfc822": _read_fixture("multipart_reply.eml")}
        stub = self.transport._normalize(raw)
        self.assertEqual(stub["email_from"], "customer@example.com")
        self.assertEqual(stub["to"], ["sales@example.com"])
        self.assertEqual(stub["cc"], ["watcher@example.com"])
        self.assertIn("<p>Thanks, that works for us.</p>", stub["body"])
        self.assertEqual(stub["in_reply_to"], "<original-msg-1@example.com>")
        self.assertIn("<thread-root@example.com>", stub["references"])
        self.assertEqual(stub["external_id"], "42")

    def test_normalize_bare_email_no_partner_escapes_plaintext(self):
        raw = {"external_id": "7", "rfc822": _read_fixture("bare_email_no_partner.eml")}
        stub = self.transport._normalize(raw)
        self.assertEqual(stub["email_from"], "stranger@example.com")
        # A plaintext body's own markup must never be interpolated raw into
        # the HTML message body -- it would otherwise be stored/rendered
        # unescaped in the conversation's chatter.
        self.assertNotIn("<script>", stub["body"])
        self.assertIn("&lt;script&gt;", stub["body"])

    def test_normalize_sanitizes_html_part(self):
        # Blocking issue #2: an inbound HTML body is untrusted input --
        # <script>/inline event handlers must never survive into the
        # inbox viewer, sanitized through Odoo's own html_sanitize.
        raw = {
            "external_id": "8",
            "rfc822": _read_fixture("html_script_injection.eml"),
        }
        stub = self.transport._normalize(raw)
        self.assertNotIn("<script", stub["body"])
        self.assertNotIn("onerror", stub["body"])
        self.assertIn("Click", stub["body"])

    def test_normalize_multipart_mixed_lists_attachment_not_inlined(self):
        # Blocking issue #2: multipart/mixed with an attachment -- the
        # body is the multipart/alternative part (get_body() skips the
        # attachment), and the attachment is listed as metadata, never
        # its encoded payload inlined into the body.
        raw = {
            "external_id": "9",
            "rfc822": _read_fixture("multipart_mixed_with_attachment.eml"),
        }
        stub = self.transport._normalize(raw)
        self.assertIn("invoice", stub["body"])
        self.assertNotIn("JVBERi0", stub["body"])  # no base64 payload inlined
        self.assertEqual(len(stub["attachments"]), 1)
        attachment = stub["attachments"][0]
        self.assertEqual(attachment["filename"], "invoice.pdf")
        self.assertEqual(attachment["content_type"], "application/pdf")
        self.assertGreater(attachment["size"], 0)

    def test_normalize_decodes_quoted_printable(self):
        raw = {
            "external_id": "10",
            "rfc822": _read_fixture("quoted_printable.eml"),
        }
        stub = self.transport._normalize(raw)
        self.assertIn("café préféré", stub["body"])
        self.assertIn("livraison prévue", stub["body"])

    def test_normalize_decodes_non_utf8_charset(self):
        raw = {
            "external_id": "11",
            "rfc822": _read_fixture("non_utf8_charset.eml"),
        }
        stub = self.transport._normalize(raw)
        self.assertIn("commande a été confirmée", stub["body"])

    def test_normalize_simple_message_has_no_attachments(self):
        raw = {"external_id": "7", "rfc822": _read_fixture("bare_email_no_partner.eml")}
        stub = self.transport._normalize(raw)
        self.assertEqual(stub["attachments"], [])


class TestConversationImapMatchInbound(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "IMAP Transport A", "provider": "imap", "login": "a@example.com"}
        )
        cls.other_transport = cls.env["conversation.transport"].create(
            {"name": "IMAP Transport B", "provider": "imap", "login": "b@example.com"}
        )
        cls.conversation = cls.env["mail.conversation"].create({"name": "Thread"})

    def _post_outbound(self, transport, message_id):
        """The state ``_record_outbound`` leaves behind: ``transport_id``
        set, the real RFC id in ``message_id``, ``external_id`` derived
        from it."""
        message = self.conversation.message_post(
            body="prior message", subtype_xmlid="mail.mt_note"
        )
        message.write(
            {
                "transport_id": transport.id,
                "message_id": message_id,
                "external_id": message_id.strip("<>"),
            }
        )
        return message

    def _post_captured(self, transport, message_id, uid="227398"):
        """The state ``_capture_stub`` leaves behind, which is NOT the
        same shape: ``transport_id`` is deliberately falsy (the
        notification-safety marker), ``external_id`` is the IMAP UID, and
        the RFC id lives in ``message_id``. Provenance therefore comes
        from the conversation's ``primary_transport_id``."""
        self.conversation.primary_transport_id = transport
        message = self.conversation.message_post(
            body="captured message", subtype_xmlid="mail.mt_note"
        )
        message.write({"message_id": message_id, "external_id": uid})
        return message

    def test_match_inbound_finds_message_within_same_transport(self):
        self._post_outbound(self.transport, "<original-msg-1@example.com>")
        raw = {"rfc822": _read_fixture("multipart_reply.eml")}
        matched = self.transport._match_inbound(raw)
        self.assertTrue(matched)
        self.assertEqual(matched.transport_id, self.transport)

    def test_match_inbound_correlates_a_quiet_captured_message(self):
        # The regression this whole method existed for and never did: a
        # captured inbound note leaves transport_id falsy on purpose, so a
        # `transport_id = self.id` domain excluded exactly the messages
        # worth correlating to, and every customer reply arrived
        # uncorrelated.
        captured = self._post_captured(
            self.transport, "<original-msg-1@example.com>"
        )
        raw = {"rfc822": _read_fixture("multipart_reply.eml")}
        matched = self.transport._match_inbound(raw)
        self.assertEqual(matched, captured)

    def test_match_inbound_matches_the_rfc_id_not_the_imap_uid(self):
        # external_id holds the IMAP UID on an email transport, so
        # correlating References against it could never succeed -- the
        # angle-bracketed id is in message_id. A message carrying ONLY the
        # UID must not match.
        message = self.conversation.message_post(
            body="prior message", subtype_xmlid="mail.mt_note"
        )
        message.write({"transport_id": self.transport.id, "external_id": "227398"})
        raw = {"rfc822": _read_fixture("multipart_reply.eml")}
        self.assertFalse(self.transport._match_inbound(raw))

    def test_match_inbound_ignores_an_ordinary_internal_note(self):
        # Every mail.message has an Odoo-generated message_id, but one no
        # correspondent has ever seen. external_id is what marks a message
        # as having travelled over a transport.
        note = self.conversation.message_post(
            body="internal note", subtype_xmlid="mail.mt_note"
        )
        note.write({"message_id": "<original-msg-1@example.com>"})
        raw = {"rfc822": _read_fixture("multipart_reply.eml")}
        self.assertFalse(self.transport._match_inbound(raw))

    def test_match_inbound_never_crosses_transport(self):
        # The matching id exists, but only on a DIFFERENT transport --
        # correlation must stay within-transport.
        self._post_outbound(self.other_transport, "<original-msg-1@example.com>")
        raw = {"rfc822": _read_fixture("multipart_reply.eml")}
        matched = self.transport._match_inbound(raw)
        self.assertFalse(matched)

    def test_match_inbound_never_crosses_transport_when_captured(self):
        # Same rule on the capture path, where provenance comes from the
        # conversation rather than the message.
        self._post_captured(self.other_transport, "<original-msg-1@example.com>")
        raw = {"rfc822": _read_fixture("multipart_reply.eml")}
        self.assertFalse(self.transport._match_inbound(raw))

    def test_match_inbound_unknown_returns_falsy(self):
        raw = {"rfc822": _read_fixture("bare_email_no_partner.eml")}
        matched = self.transport._match_inbound(raw)
        self.assertFalse(matched)


class FakeBrowseIMAP:
    """A minimal IMAP SELECT/UID SEARCH/FETCH fake -- just enough surface
    for ``_browse`` to page through a mailbox without a real socket.
    Distinct from FakeOAuthIMAP/FakeGmailIMAP below, which only cover the
    connection/auth layer (``authenticate``) and stub out ``uid()``
    entirely.

    Records what it was asked for (``selected``, ``searches``) so a test
    can assert the *shape* of the conversation with the server, not just
    the rows that came back."""

    # ordered oldest -> newest: list of (uid_bytes, header_bytes).
    # Sequence numbers are 1-based positions in this list.
    messages = []
    selected = None
    selects = []
    searches = []
    timeouts = []
    fetch_calls = []

    def __init__(self, host, port, timeout=None):
        FakeBrowseIMAP.timeouts.append(timeout)

    def login(self, user, password):
        pass

    def select(self, mailbox):
        FakeBrowseIMAP.selected = mailbox
        FakeBrowseIMAP.selects.append(mailbox)
        return "OK", [str(len(FakeBrowseIMAP.messages)).encode()]

    def uid(self, command, *args):
        if command == "search":
            criteria = args[-1]
            FakeBrowseIMAP.searches.append(criteria)
            if criteria == "ALL":
                selected = FakeBrowseIMAP.messages
            else:
                # only the sequence-range form this engine issues
                low, high = (int(part) for part in criteria.split(":"))
                selected = FakeBrowseIMAP.messages[low - 1 : high]
            return "OK", [b" ".join(uid for uid, _headers in selected)]
        if command == "fetch":
            # A real server takes a UID *set* and answers with one part
            # per message, each carrying its own UID, interleaved with
            # bare b")" terminators -- and in no guaranteed order.
            target = args[0]
            if isinstance(target, bytes):
                target = target.decode()
            requested = [u.strip() for u in str(target).split(",") if u.strip()]
            FakeBrowseIMAP.fetch_calls.append(requested)
            parts = []
            for candidate_uid, headers in reversed(FakeBrowseIMAP.messages):
                uid = candidate_uid.decode()
                if uid in requested:
                    parts.append(
                        (
                            b"1 (UID %s BODY[HEADER.FIELDS ...] {%d}"
                            % (uid.encode(), len(headers)),
                            headers,
                        )
                    )
                    parts.append(b")")
            return "OK", parts or [None]
        raise AssertionError("unexpected IMAP command %r" % (command,))

    def close(self):
        pass

    def logout(self):
        pass


class TestConversationImapBrowse(TransactionCase):
    """Test plan #1 / blocking issue #1 (redo item 1, AC1/AC3/AC5):
    ``_browse`` is what ``browse_page`` -- the RPC the OWL inbox client
    calls to open an account's inbox -- actually delegates to. The
    existing OAuth-connection tests below only prove the connection/auth
    layer connects (the specific regression that was fixed); the
    base-level dispatch tests in conversation_base mock ``_browse`` out
    entirely. Neither exercises the real IMAP UID SEARCH + per-message
    header FETCH + pagination logic that assembles what a human actually
    sees when "the inbox opens" -- covered here end to end."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Browse Transport",
                "provider": "imap",
                "browsable": True,
                "login": "sales@example.com",
                "imap_host": "imap.example.com",
            }
        )

    def setUp(self):
        super().setUp()
        # The envelope cache is module-level and per-process by design
        # (that is what makes a second page view free), so it survives
        # between tests -- clear it or the FETCH under test never runs.
        _ENVELOPE_CACHE.clear()
        FakeBrowseIMAP.selected = None
        FakeBrowseIMAP.selects = []
        FakeBrowseIMAP.searches = []
        FakeBrowseIMAP.fetch_calls = []
        FakeBrowseIMAP.messages = [
            (
                str(n).encode(),
                (
                    "From: customer%d@example.com\r\n"
                    "To: sales@example.com\r\n"
                    "Subject: Message %d\r\n"
                    "Message-Id: <msg-%d@example.com>\r\n\r\n" % (n, n, n)
                ).encode(),
            )
            for n in range(1, 4)
        ]
        patcher = patch.object(
            type(self.transport), "_get_imap_client_class", return_value=FakeBrowseIMAP
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        page_size_patcher = patch.object(
            type(self.transport), "_imap_page_size", return_value=2
        )
        page_size_patcher.start()
        self.addCleanup(page_size_patcher.stop)

    def test_browse_returns_newest_first_paginated_stubs(self):
        page = self.transport._browse(page=1)
        self.assertEqual(page["page"], 1)
        self.assertEqual(page["page_size"], 2)
        self.assertTrue(page["has_more"])
        self.assertEqual(len(page["items"]), 2)
        # newest first: uid 3, then uid 2 (uid 1 held for page 2)
        self.assertEqual(page["items"][0]["external_id"], "3")
        self.assertEqual(page["items"][0]["subject"], "Message 3")
        self.assertEqual(page["items"][0]["email_from"], "customer3@example.com")
        self.assertEqual(page["items"][1]["external_id"], "2")

    def test_browse_second_page_has_no_more(self):
        page = self.transport._browse(page=2)
        self.assertEqual(len(page["items"]), 1)
        self.assertEqual(page["items"][0]["external_id"], "1")
        self.assertFalse(page["has_more"])

    def test_browse_reads_the_whole_page_in_one_round_trip(self):
        # IMAP is request/response on one connection, so one FETCH per
        # message costs N sequential round trips -- measured at 92s for a
        # 25-message page against a live Gmail account. One UID set costs
        # one.
        page = self.transport._browse(page=1)
        self.assertEqual(len(page["items"]), 2)
        self.assertEqual(len(FakeBrowseIMAP.fetch_calls), 1)
        self.assertEqual(sorted(FakeBrowseIMAP.fetch_calls[0]), ["2", "3"])

    def test_browse_selects_the_mailbox_only_once(self):
        # SELECT is the expensive command on a large mailbox -- seconds on
        # a Gmail folder of any size, and the dominant cost of a page now
        # that the FETCH is a single round trip. The count it returns is
        # the only thing paging needs from it, so asking twice doubles the
        # dominant cost to re-learn a number the first one already gave us.
        self.transport._browse(page=1)
        self.assertEqual(FakeBrowseIMAP.selects, ['"INBOX"'])

    def test_browse_restores_order_the_server_did_not_keep(self):
        # The fake answers in the opposite order on purpose: newest-first
        # is the caller's contract, not something the server guarantees.
        page = self.transport._browse(page=1)
        self.assertEqual(
            [item["external_id"] for item in page["items"]], ["3", "2"]
        )

    def test_browse_never_asks_the_server_for_every_uid(self):
        # UID SEARCH ALL answers with every UID in the mailbox on a single
        # line, and imaplib refuses to read a line past 1 MB -- so opening
        # a real inbox failed outright, after transferring megabytes to
        # show one page. Each page must ask only for its own window.
        self.transport._browse(page=1)
        self.assertNotIn("ALL", FakeBrowseIMAP.searches)
        self.assertEqual(FakeBrowseIMAP.searches, ["2:3"])

    def test_browse_quotes_the_mailbox_name(self):
        # Gmail's special folders all contain a space; imaplib passes the
        # mailbox through verbatim, so an unquoted name is parsed as two
        # arguments and the SELECT fails.
        self.transport.imap_folder = "[Gmail]/All Mail"
        self.transport._browse(page=1)
        self.assertEqual(FakeBrowseIMAP.selected, '"[Gmail]/All Mail"')

    def test_browse_page_beyond_the_end_is_empty(self):
        page = self.transport._browse(page=9)
        self.assertEqual(page["items"], [])
        self.assertFalse(page["has_more"])

    def test_browse_page_rpc_reaches_real_browse_implementation(self):
        # Unlike conversation_base's dispatch test (which patches _browse
        # out), this confirms the RPC entry point a human's inbox click
        # actually resolves to reaches this real, connected implementation.
        result = self.transport.browse_page(self.transport.id, page=1)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["external_id"], "3")


class FakeSMTP:
    """Records the outgoing message instead of opening a real socket."""

    sent = []
    envelopes = []
    timeouts = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        FakeSMTP.timeouts.append(timeout)

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message, to_addrs=None):
        FakeSMTP.sent.append(message)
        FakeSMTP.envelopes.append(to_addrs)

    def quit(self):
        pass


class TestConversationImapSend(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "IMAP Send Transport",
                "provider": "imap",
                "sendable": True,
                "login": "sales@example.com",
                "smtp_host": "smtp.example.com",
            }
        )
        cls.conversation = cls.env["mail.conversation"].create(
            {"name": "Send Conversation", "primary_transport_id": cls.transport.id}
        )

    def setUp(self):
        super().setUp()
        FakeSMTP.sent = []
        FakeSMTP.envelopes = []
        patcher = patch.object(
            type(self.transport), "_get_smtp_client_class", return_value=FakeSMTP
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_send_delivers_to_explicit_recipients_and_records_metadata(self):
        message = self.conversation.action_reply(
            "<p>Here you go</p>", recipients=["explicit@example.com"]
        )
        self.assertEqual(len(FakeSMTP.sent), 1)
        outgoing = FakeSMTP.sent[0]
        self.assertEqual(str(outgoing["To"]), "explicit@example.com")
        self.assertEqual(message.transport_id, self.transport)
        self.assertTrue(message.external_id)

    def test_outbound_carries_the_messages_own_message_id(self):
        # Minting a second Message-Id at send time left mail.message
        # holding an id that was never on the wire, so a recipient's
        # In-Reply-To could never be correlated back to it.
        message = self.conversation.action_reply(
            "<p>Here you go</p>", recipients=["explicit@example.com"]
        )
        self.assertEqual(str(FakeSMTP.sent[0]["Message-Id"]), message.message_id)

    def test_outbound_is_multipart_alternative_with_a_plaintext_part(self):
        self.conversation.action_reply(
            "<p>Here you go</p>", recipients=["explicit@example.com"]
        )
        outgoing = FakeSMTP.sent[0]
        self.assertEqual(outgoing.get_content_type(), "multipart/alternative")
        plain = outgoing.get_body(preferencelist=("plain",))
        self.assertIsNotNone(plain)
        self.assertIn("Here you go", plain.get_content())

    def test_outbound_local_links_are_made_absolute(self):
        # A composer file link ships as a root-relative /web/content/...,
        # which resolves against the recipient's own mail client and
        # arrives dead. Same rewrite mail_mail does before sending.
        self.conversation.action_reply(
            '<p>See <a href="/web/content/42">the file</a></p>',
            recipients=["explicit@example.com"],
        )
        html = FakeSMTP.sent[0].get_body(preferencelist=("html",)).get_content()
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        self.assertNotIn('href="/web/content/42"', html)
        self.assertIn("%s/web/content/42" % base_url, html)


class FakeAppendIMAP:
    """Records APPEND calls (and satisfies the connection helpers)."""

    appends = []

    def __init__(self, host, port, timeout=None):
        pass

    def login(self, user, password):
        pass

    def select(self, mailbox):
        return "OK", [b"0"]

    def append(self, mailbox, flags, date_time, message):
        FakeAppendIMAP.appends.append((mailbox, flags, message))
        return "OK", [b"APPEND completed"]

    def close(self):
        pass

    def logout(self):
        pass


class TestConversationImapSendRaw(TransactionCase):
    """The send primitive (task #3965, piece 2): triage from a personal
    mailbox must be able to reply WITHOUT filing the exchange into the
    shared hub, which is only possible if sending is separable from
    persisting."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Raw Send Transport",
                "provider": "imap",
                "sendable": True,
                "login": "sales@example.com",
                "imap_host": "imap.example.com",
                "smtp_host": "smtp.example.com",
            }
        )

    def setUp(self):
        super().setUp()
        FakeSMTP.sent = []
        FakeSMTP.envelopes = []
        FakeAppendIMAP.appends = []
        for attr, fake in (
            ("_get_smtp_client_class", FakeSMTP),
            ("_get_imap_client_class", FakeAppendIMAP),
        ):
            patcher = patch.object(type(self.transport), attr, return_value=fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_send_raw_persists_nothing_in_odoo(self):
        before = (
            self.env["mail.conversation"].search_count([]),
            self.env["mail.message"].search_count([]),
            self.env["mail.mail"].search_count([]),
        )
        self.transport._send_raw(
            subject="Quick answer",
            body="<p>No need to file this.</p>",
            to_emails=["customer@example.com"],
        )
        self.assertEqual(len(FakeSMTP.sent), 1)
        self.assertEqual(
            before,
            (
                self.env["mail.conversation"].search_count([]),
                self.env["mail.message"].search_count([]),
                self.env["mail.mail"].search_count([]),
            ),
        )

    def test_bcc_reaches_the_envelope_but_never_a_header(self):
        self.transport._send_raw(
            subject="Discreet",
            body="<p>hi</p>",
            to_emails=["customer@example.com"],
            cc=["watcher@example.com"],
            bcc=["secret@example.com"],
        )
        outgoing = FakeSMTP.sent[0]
        self.assertIsNone(outgoing["Bcc"])
        self.assertNotIn("secret@example.com", outgoing.as_string())
        self.assertEqual(
            FakeSMTP.envelopes[0],
            ["customer@example.com", "watcher@example.com", "secret@example.com"],
        )

    def test_attachments_are_real_mime_parts(self):
        self.transport._send_raw(
            subject="With a file",
            body="<p>see attached</p>",
            to_emails=["customer@example.com"],
            attachments=[
                {
                    "filename": "quote.pdf",
                    "content": b"%PDF-1.4 fake",
                    "mimetype": "application/pdf",
                }
            ],
        )
        parts = list(FakeSMTP.sent[0].iter_attachments())
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].get_filename(), "quote.pdf")
        self.assertEqual(parts[0].get_content_type(), "application/pdf")
        self.assertEqual(parts[0].get_payload(decode=True), b"%PDF-1.4 fake")

    def test_sent_copy_is_appended_for_a_provider_that_saves_none(self):
        # Generic IMAP/SMTP saves nothing on its own, so without this an
        # unfiled reply -- the composer default -- would exist nowhere at
        # all: sent, but persisted on neither side.
        self.transport._send_raw(
            subject="Filed to Sent",
            body="<p>hi</p>",
            to_emails=["customer@example.com"],
        )
        self.assertEqual(len(FakeAppendIMAP.appends), 1)
        mailbox, flags, raw = FakeAppendIMAP.appends[0]
        self.assertEqual(mailbox, '"Sent"')
        self.assertIn("\\Seen", flags)
        self.assertIn(b"Filed to Sent", raw)

    def test_blank_sent_folder_skips_the_append(self):
        self.transport.imap_sent_folder = False
        self.transport._send_raw(
            subject="No copy",
            body="<p>hi</p>",
            to_emails=["customer@example.com"],
        )
        self.assertEqual(len(FakeSMTP.sent), 1)
        self.assertFalse(FakeAppendIMAP.appends)

    def test_sent_folder_name_is_quoted(self):
        self.transport.imap_sent_folder = "Sent Items"
        self.transport._send_raw(
            subject="Quoted folder",
            body="<p>hi</p>",
            to_emails=["customer@example.com"],
        )
        self.assertEqual(FakeAppendIMAP.appends[0][0], '"Sent Items"')


class TestConversationImapReplyThreading(TransactionCase):
    """The In-Reply-To fix (task #3965): a captured inbox item's
    ``external_id`` is its IMAP UID -- a per-mailbox integer -- so
    threading an outbound reply against it produced a malformed
    ``In-Reply-To: 227398`` that matches nothing in the recipient's
    client. The reply must quote the captured email's real RFC822
    Message-Id."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Threading Transport",
                "provider": "imap",
                "sendable": True,
                "login": "sales@example.com",
                "smtp_host": "smtp.example.com",
            }
        )

    def setUp(self):
        super().setUp()
        FakeSMTP.sent = []
        FakeSMTP.envelopes = []
        patcher = patch.object(
            type(self.transport), "_get_smtp_client_class", return_value=FakeSMTP
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _capture(self):
        return self.env["mail.conversation"]._capture_stub(
            self.transport,
            {
                "external_id": "227398",  # the IMAP UID
                "message_id": "<real-inbound-1@example.com>",
                "subject": "Quote request",
                "body": "<p>Could you quote this?</p>",
                "email_from": "customer@example.com",
                "to": ["sales@example.com"],
                "cc": [],
            },
        )

    def test_capture_keeps_both_ids_distinct(self):
        conversation = self._capture()
        captured = conversation.message_ids.filtered(lambda m: m.external_id)
        self.assertEqual(captured.external_id, "227398")
        self.assertEqual(captured.message_id, "<real-inbound-1@example.com>")

    def test_reply_threads_on_the_rfc_message_id_not_the_uid(self):
        conversation = self._capture()
        conversation.action_reply(
            "<p>Certainly.</p>", recipients=["customer@example.com"]
        )
        outgoing = FakeSMTP.sent[0]
        self.assertEqual(
            str(outgoing["In-Reply-To"]), "<real-inbound-1@example.com>"
        )
        self.assertEqual(
            str(outgoing["References"]), "<real-inbound-1@example.com>"
        )

    def test_reply_ignores_an_internal_note_that_never_left_odoo(self):
        # An ordinary internal note also carries an Odoo-generated
        # message_id, but no correspondent has ever seen it -- threading
        # against it would break the thread rather than continue it.
        conversation = self._capture()
        conversation.message_post(body="internal", subtype_xmlid="mail.mt_note")
        conversation.action_reply(
            "<p>Certainly.</p>", recipients=["customer@example.com"]
        )
        self.assertEqual(
            str(FakeSMTP.sent[0]["In-Reply-To"]), "<real-inbound-1@example.com>"
        )


class FakeOAuthIMAP:
    """Records auth calls; simulates a first-attempt auth failure to
    exercise the token-refresh-then-retry path."""

    fail_once = False
    authenticate_calls = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port

    def authenticate(self, mechanism, callback):
        FakeOAuthIMAP.authenticate_calls.append((mechanism, callback(b"")))
        if FakeOAuthIMAP.fail_once and len(FakeOAuthIMAP.authenticate_calls) == 1:
            raise imaplib.IMAP4.error("token expired")

    def select(self, mailbox):
        return "OK", [b"0"]

    def close(self):
        pass

    def logout(self):
        pass


class TestConversationImapOAuthConnection(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "OAuth-Capable IMAP Transport",
                "provider": "imap",
                "browsable": True,
                "login": "oauth-user@example.com",
                "imap_host": "imap.example.com",
            }
        )

    def setUp(self):
        super().setUp()
        FakeOAuthIMAP.authenticate_calls = []
        FakeOAuthIMAP.fail_once = False
        patcher = patch.object(
            type(self.transport), "_get_imap_client_class", return_value=FakeOAuthIMAP
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_oauth_string_used_instead_of_password_login(self):
        oauth_patcher = patch.object(
            type(self.transport),
            "_imap_oauth_string",
            return_value="user=oauth-user@example.com\1auth=Bearer token\1\1",
        )
        oauth_patcher.start()
        self.addCleanup(oauth_patcher.stop)
        with self.transport._imap_connection():
            pass
        self.assertEqual(len(FakeOAuthIMAP.authenticate_calls), 1)
        mechanism, sasl_response = FakeOAuthIMAP.authenticate_calls[0]
        self.assertEqual(mechanism, "XOAUTH2")
        self.assertIn(b"Bearer token", sasl_response)

    def test_auth_failure_refreshes_token_and_retries_once(self):
        FakeOAuthIMAP.fail_once = True
        calls = []

        def _oauth_string(self, force_refresh=False):
            calls.append(force_refresh)
            token = "refreshed-token" if force_refresh else "stale-token"
            return "user=oauth-user@example.com\1auth=Bearer %s\1\1" % token

        oauth_patcher = patch.object(
            type(self.transport), "_imap_oauth_string", _oauth_string
        )
        oauth_patcher.start()
        self.addCleanup(oauth_patcher.stop)
        with self.transport._imap_connection():
            pass
        self.assertEqual(len(FakeOAuthIMAP.authenticate_calls), 2)
        self.assertIn(b"Bearer stale-token", FakeOAuthIMAP.authenticate_calls[0][1])
        self.assertIn(
            b"Bearer refreshed-token", FakeOAuthIMAP.authenticate_calls[1][1]
        )
        self.assertEqual(calls, [False, True])

    def test_no_oauth_string_falls_back_to_password_guard_unchanged(self):
        # No _imap_oauth_string override and no imap_host/login on a
        # fresh transport -- the original guard fires verbatim.
        bare = self.env["conversation.transport"].create(
            {"name": "Bare IMAP", "provider": "imap"}
        )
        with self.assertRaises(UserError):
            with bare._imap_connection():
                pass


class TestConversationImapSocketTimeouts(TransactionCase):
    """imaplib and smtplib default to NO socket timeout, so a mail server
    that stops answering holds an Odoo worker until the request watchdog
    fires -- commonly 20 minutes. With N workers, N such requests take the
    whole instance down, health checks included, and a container gets
    killed by its liveness probe. Every connection must be bounded."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Timeout Transport",
                "provider": "imap",
                "browsable": True,
                "sendable": True,
                "login": "sales@example.com",
                "imap_host": "imap.example.com",
                "smtp_host": "smtp.example.com",
            }
        )

    def setUp(self):
        super().setUp()
        FakeBrowseIMAP.messages = []
        FakeBrowseIMAP.timeouts = []
        FakeSMTP.sent = []
        FakeSMTP.envelopes = []
        FakeSMTP.timeouts = []
        for attr, fake in (
            ("_get_imap_client_class", FakeBrowseIMAP),
            ("_get_smtp_client_class", FakeSMTP),
        ):
            patcher = patch.object(type(self.transport), attr, return_value=fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_imap_connections_are_bounded(self):
        self.transport._browse(page=1)
        self.assertTrue(FakeBrowseIMAP.timeouts)
        for timeout in FakeBrowseIMAP.timeouts:
            self.assertTrue(timeout, "IMAP connected with no socket timeout")
            self.assertGreater(timeout, 0)

    def test_smtp_connections_are_bounded(self):
        self.transport._send_raw(
            subject="Bounded",
            body="<p>hi</p>",
            to_emails=["customer@example.com"],
        )
        self.assertTrue(FakeSMTP.timeouts)
        for timeout in FakeSMTP.timeouts:
            self.assertTrue(timeout, "SMTP connected with no socket timeout")
            self.assertGreater(timeout, 0)

    def test_timeout_stays_within_a_liveness_probe_budget(self):
        # A stall longer than the probe's patience is a restart, not a
        # slow page: every worker can be stuck at most this long at once.
        self.assertLessEqual(self.transport._email_socket_timeout(), 45)


class TestConversationImapConnectionParams(TransactionCase):
    """Refactor guard (task #3965): this module now supplies only the
    connection *configuration* for the shared conversation_email_base
    engine, and does so guarded on its own provider value -- so a
    transport belonging to another provider installed alongside (Gmail's,
    with its own fixed endpoints) is never routed through these fields."""

    def test_connection_params_come_from_this_providers_own_fields(self):
        transport = self.env["conversation.transport"].create(
            {
                "name": "Params Transport",
                "provider": "imap",
                "login": "sales@example.com",
                "imap_host": "imap.example.com",
                "imap_port": 1993,
                "smtp_host": "smtp.example.com",
                "smtp_port": 2587,
                "smtp_ssl": False,
                "password": "secret",
            }
        )
        params = transport._email_connection_params()
        self.assertEqual(params["imap_host"], "imap.example.com")
        self.assertEqual(params["imap_port"], 1993)
        self.assertEqual(params["smtp_host"], "smtp.example.com")
        self.assertEqual(params["smtp_port"], 2587)
        self.assertFalse(params["smtp_starttls"])
        self.assertEqual(params["password"], "secret")


class TestConversationImapViewSmoke(TransactionCase):
    def test_form_builds_with_imap_fields(self):
        with Form(self.env["conversation.transport"]) as form:
            form.name = "Smoke Transport"
            form.provider = "imap"
            form.imap_host = "imap.example.com"
            form.smtp_host = "smtp.example.com"
            form.password = "secret"
        transport = form.save()
        self.assertEqual(transport.imap_host, "imap.example.com")
