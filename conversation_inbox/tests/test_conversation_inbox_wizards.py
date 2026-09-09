# Acceptance criteria (task #3965, AC6 a/b/c/e/f/g -- the GTD funnel's
# dialog wizards):
#   - capture wizard: new / existing / link modes file the stub correctly,
#     with an optional same-step reassign.
#   - reassign wizard: hands a captured (or not-yet-captured, capture-on-
#     demand) item to a user/team.
#   - reply wizard: reply / reply-all / forward all go through the
#     transport's _send (never Odoo's own notification pipeline), and a
#     repeat action on the same external_id never files a second
#     conversation (idempotent capture).

import base64
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class InboxWizardTestMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Inbox Test Transport",
                "browsable": True,
                "sendable": True,
                "login": "sales@example.com",
            }
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Customer Corp", "email": "customer@example.com"}
        )

    RFC822 = (
        b"From: Customer Corp <customer@example.com>\r\n"
        b"To: sales@example.com\r\n"
        b"Subject: Need a quote\r\n"
        b"Message-Id: <original-1@example.com>\r\n"
        b'Content-Type: multipart/mixed; boundary="B"\r\n\r\n'
        b"--B\r\n"
        b"Content-Type: text/plain\r\n\r\n"
        b"Please send a quote.\r\n"
        b"--B\r\n"
        b"Content-Type: application/pdf\r\n"
        b"Content-Disposition: attachment; filename=\"spec.pdf\"\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\n"
        b"JVBERi0xLjQK\r\n"
        b"--B--\r\n"
    )

    def _mock_fetch_normalize(self, external_id="ext-1", **overrides):
        stub = {
            "subject": "Need a quote",
            "body": "<p>Please send a quote.</p>",
            "email_from": "customer@example.com",
            "to": ["sales@example.com"],
            "cc": ["watcher@example.com"],
            "external_id": external_id,
            "message_id": "<original-1@example.com>",
            "date": False,
            "attachments": [
                {
                    "filename": "spec.pdf",
                    "content_type": "application/pdf",
                    "size": 9,
                }
            ],
        }
        stub.update(overrides)
        transport_model = type(self.transport)
        return patch.object(
            transport_model,
            "_fetch",
            return_value={"external_id": external_id, "rfc822": self.RFC822},
            autospec=True,
        ), patch.object(transport_model, "_normalize", return_value=stub, autospec=True)


class TestConversationInboxCaptureWizard(InboxWizardTestMixin, TransactionCase):
    def test_capture_new_conversation(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize()
        wizard = self.env["conversation.inbox.capture.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-1",
                "mode": "new",
            }
        )
        with fetch_patch, normalize_patch:
            action = wizard.action_capture()
        conversation = self.env["mail.conversation"].browse(action["res_id"])
        self.assertEqual(conversation.name, "Need a quote")
        self.assertEqual(conversation.primary_transport_id, self.transport)

    def test_capture_existing_requires_target(self):
        wizard = self.env["conversation.inbox.capture.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-1",
                "mode": "existing",
            }
        )
        with self.assertRaises(UserError):
            wizard.action_capture()

    def test_capture_link_requires_target(self):
        wizard = self.env["conversation.inbox.capture.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-1",
                "mode": "link",
            }
        )
        with self.assertRaises(UserError):
            wizard.action_capture()

    def test_capture_with_reassign_in_same_step(self):
        other_user = self.env["res.users"].create(
            {
                "name": "Triage User",
                "login": "triage_user_test@example.com",
                "email": "triage_user_test@example.com",
            }
        )
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-2")
        wizard = self.env["conversation.inbox.capture.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-2",
                "mode": "new",
                "user_id": other_user.id,
            }
        )
        with fetch_patch, normalize_patch:
            action = wizard.action_capture()
        conversation = self.env["mail.conversation"].browse(action["res_id"])
        self.assertEqual(conversation.user_id, other_user)


class TestConversationInboxReassignWizard(InboxWizardTestMixin, TransactionCase):
    def test_reassign_captures_on_demand(self):
        other_user = self.env["res.users"].create(
            {
                "name": "Reassignee",
                "login": "reassignee_test@example.com",
                "email": "reassignee_test@example.com",
            }
        )
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-3")
        wizard = self.env["conversation.inbox.reassign.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-3",
                "user_id": other_user.id,
            }
        )
        with fetch_patch, normalize_patch:
            action = wizard.action_reassign()
        conversation = self.env["mail.conversation"].browse(action["res_id"])
        self.assertEqual(conversation.user_id, other_user)

    def test_reassign_requires_user_or_team(self):
        wizard = self.env["conversation.inbox.reassign.wizard"].create(
            {"transport_id": self.transport.id, "external_id": "ext-3"}
        )
        with self.assertRaises(UserError):
            wizard.action_reassign()

    def test_reassign_reuses_already_captured_conversation(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-4")
        with fetch_patch, normalize_patch:
            first = self.env["mail.conversation"]._capture_or_find(
                self.transport, "ext-4"
            )
        other_user = self.env["res.users"].create(
            {
                "name": "Second Assignee",
                "login": "second_assignee_test@example.com",
                "email": "second_assignee_test@example.com",
            }
        )
        wizard = self.env["conversation.inbox.reassign.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-4",
                "user_id": other_user.id,
            }
        )
        action = wizard.action_reassign()
        self.assertEqual(
            action["res_id"],
            first.id,
            "reassigning an already-captured item must not file a duplicate",
        )


class TestConversationInboxReplyWizard(InboxWizardTestMixin, TransactionCase):
    """The rebuilt composer (task #3965, piece 2). The default path files
    NOTHING in Odoo: a personal mailbox's traffic must not land in the
    shared hub unless the user asks for it."""

    def _mock_send_raw(self):
        return patch.object(
            type(self.transport),
            "_send_raw",
            return_value="<sent-1@example.com>",
            autospec=True,
        )

    def _open(self, external_id, action_type, **values):
        """Open the composer the way the client does -- through
        default_get -- so the prefilling is exercised, not bypassed."""
        context = {
            "default_transport_id": self.transport.id,
            "default_external_id": external_id,
            "default_action_type": action_type,
        }
        return (
            self.env["conversation.inbox.reply.wizard"]
            .with_context(**context)
            .create(values)
        )

    # -- prefilling -------------------------------------------------

    def test_reply_prefills_sender_subject_and_quoted_original(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-5")
        with fetch_patch, normalize_patch:
            wizard = self._open("ext-5", "reply")
        self.assertEqual(wizard.to_emails, "customer@example.com")
        self.assertFalse(wizard.cc_emails)
        self.assertEqual(wizard.subject, "Re: Need a quote")
        self.assertEqual(wizard.in_reply_to, "<original-1@example.com>")
        # The original is quoted into the EDITABLE body, so the user can
        # trim it -- not appended at send time behind their back.
        self.assertIn("Please send a quote.", wizard.body)
        self.assertIn("blockquote", wizard.body)

    def test_reply_all_carries_the_others_but_never_this_account(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-6")
        with fetch_patch, normalize_patch:
            wizard = self._open("ext-6", "reply_all")
        self.assertEqual(wizard.to_emails, "customer@example.com")
        self.assertIn("watcher@example.com", wizard.cc_emails)
        # sales@example.com is this transport's own login: replying all to
        # yourself is noise, and on a shared mailbox it is a loop.
        self.assertNotIn("sales@example.com", wizard.cc_emails)

    def test_forward_leaves_recipient_empty_and_lists_the_originals_files(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-7")
        with fetch_patch, normalize_patch:
            wizard = self._open("ext-7", "forward")
        self.assertFalse(wizard.to_emails)
        self.assertEqual(wizard.subject, "Fwd: Need a quote")
        self.assertEqual(wizard.forwarded_filenames, "spec.pdf")
        self.assertIn("Forwarded message", wizard.body)

    def test_subject_prefix_is_not_stacked_on_a_reply_to_a_reply(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(
            external_id="ext-10", subject="Re: Need a quote"
        )
        with fetch_patch, normalize_patch:
            wizard = self._open("ext-10", "reply")
        self.assertEqual(wizard.subject, "Re: Need a quote")

    def test_filing_default_follows_the_transport(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-11")
        with fetch_patch, normalize_patch:
            wizard = self._open("ext-11", "reply")
        self.assertFalse(wizard.file_in_odoo)
        self.transport.default_file_in_odoo = True
        with fetch_patch, normalize_patch:
            shared = self._open("ext-11", "reply")
        self.assertTrue(shared.file_in_odoo)

    # -- sending ----------------------------------------------------

    def _attachment(self, name="quote.pdf"):
        """A file the user added in the composer, as the many2many_binary
        widget creates it: an ordinary ir.attachment pointing at the
        wizard."""
        return self.env["ir.attachment"].create(
            {
                "name": name,
                "datas": base64.b64encode(b"%PDF-1.4 tiny"),
                "res_model": "conversation.inbox.reply.wizard",
                "res_id": 0,
            }
        )

    def test_unfiled_send_leaves_no_wizard_row_and_no_attachment(self):
        # "Nothing is recorded in Odoo" has to be true of the DATABASE,
        # not just of mail.message. The wizard is a TransientModel whose
        # row holds the draft, the recipients AND the Bcc list, and its
        # attachments are ordinary ir.attachment records. Left alone the
        # row survives until the DAILY autovacuum cron, and the
        # attachments survive forever -- orphaned but never collected,
        # since the filestore GC only removes files no attachment row
        # references.
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-17")
        attachment = self._attachment()
        with fetch_patch, normalize_patch:
            wizard = self._open(
                "ext-17",
                "reply",
                body="<p>Sure.</p>",
                bcc_emails="quiet@example.com",
                attachment_ids=[(6, 0, attachment.ids)],
            )
            with self._mock_send_raw():
                wizard.action_send()
        self.assertFalse(wizard.exists(), "the composer row must not outlive the send")
        self.assertFalse(attachment.exists(), "the attached file must go with it")

    def test_filed_send_keeps_the_files_on_the_conversation(self):
        # The counterpart: when the exchange IS filed, the files that went
        # out belong on it -- a body saying "see attached" referring to
        # nothing is not a record of what was sent. They must also be
        # re-homed, since message_post only re-points attachments that
        # came from mail.compose.message/mail.scheduled.message and would
        # otherwise leave these pointing at the row we are about to drop.
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-18")
        attachment = self._attachment()
        with fetch_patch, normalize_patch:
            wizard = self._open(
                "ext-18",
                "reply",
                body="<p>Attached.</p>",
                file_in_odoo=True,
                attachment_ids=[(6, 0, attachment.ids)],
            )
            with self._mock_send_raw():
                action = wizard.action_send()
        conversation = self.env["mail.conversation"].browse(action["res_id"])
        outbound = conversation.message_ids.filtered(lambda m: m.transport_id)
        self.assertEqual(outbound.attachment_ids, attachment)
        self.assertEqual(attachment.res_model, "mail.conversation")
        self.assertEqual(attachment.res_id, conversation.id)
        self.assertFalse(wizard.exists(), "the composer row still holds the Bcc list")

    def test_unfiled_reply_persists_nothing_in_odoo(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-12")
        before = (
            self.env["mail.conversation"].search_count([]),
            self.env["mail.message"].search_count([]),
            self.env["mail.mail"].search_count([]),
        )
        with fetch_patch, normalize_patch:
            wizard = self._open("ext-12", "reply", body="<p>Sure.</p>")
            with self._mock_send_raw() as mocked:
                action = wizard.action_send()
        mocked.assert_called_once()
        self.assertEqual(action["type"], "ir.actions.act_window_close")
        self.assertEqual(
            before,
            (
                self.env["mail.conversation"].search_count([]),
                self.env["mail.message"].search_count([]),
                self.env["mail.mail"].search_count([]),
            ),
        )

    def test_send_goes_through_the_transport_not_the_notification_pipeline(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-14")
        with fetch_patch, normalize_patch:
            wizard = self._open("ext-14", "reply", body="<p>Sure.</p>")
            with self._mock_send_raw() as mocked:
                wizard.action_send()
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["to_emails"], ["customer@example.com"])
        self.assertEqual(kwargs["in_reply_to"], "<original-1@example.com>")

    def test_bcc_is_sent_but_never_recorded_when_filing(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-15")
        with fetch_patch, normalize_patch:
            wizard = self._open(
                "ext-15",
                "reply",
                body="<p>Sure.</p>",
                bcc_emails="secret@example.com",
                file_in_odoo=True,
            )
            with self._mock_send_raw() as mocked:
                action = wizard.action_send()
        self.assertEqual(mocked.call_args.kwargs["bcc"], ["secret@example.com"])
        conversation = self.env["mail.conversation"].browse(action["res_id"])
        # Filing an exchange into a shared hub must not disclose who was
        # blind-copied -- that is the one thing a Bcc promises.
        self.assertNotIn(
            "secret@example.com", conversation.participant_ids.mapped("email")
        )

    def test_filed_reply_records_the_original_and_our_answer(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-16")
        with fetch_patch, normalize_patch:
            wizard = self._open(
                "ext-16", "reply", body="<p>Sure.</p>", file_in_odoo=True
            )
            with self._mock_send_raw():
                action = wizard.action_send()
        conversation = self.env["mail.conversation"].browse(action["res_id"])
        bodies = conversation.message_ids.mapped("body")
        self.assertTrue(any("Please send a quote." in body for body in bodies))
        self.assertTrue(any("Sure." in body for body in bodies))
        outbound = conversation.message_ids.filtered(
            lambda m: m.transport_id == self.transport
        )
        # The id that actually went out, so a reply quoting it correlates
        # back to this conversation.
        self.assertEqual(outbound.message_id, "<sent-1@example.com>")

    def test_filing_into_an_existing_conversation(self):
        target = self.env["mail.conversation"].create({"name": "Existing thread"})
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-17")
        with fetch_patch, normalize_patch:
            wizard = self._open(
                "ext-17",
                "reply",
                body="<p>Sure.</p>",
                file_in_odoo=True,
                filing_mode="existing",
                conversation_id=target.id,
            )
            with self._mock_send_raw():
                action = wizard.action_send()
        self.assertEqual(action["res_id"], target.id)

    def test_filing_into_an_existing_conversation_requires_one(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-18")
        with fetch_patch, normalize_patch:
            wizard = self._open(
                "ext-18",
                "reply",
                body="<p>Sure.</p>",
                file_in_odoo=True,
                filing_mode="existing",
            )
            with self._mock_send_raw():
                with self.assertRaises(UserError):
                    wizard.action_send()

    def test_send_requires_a_recipient(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-19")
        with fetch_patch, normalize_patch:
            wizard = self._open("ext-19", "forward", body="<p>FYI</p>")
            with self.assertRaises(UserError):
                wizard.action_send()

    def test_forward_without_a_comment_still_sends(self):
        # Passing an email along with nothing added is ordinary use.
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-20")
        with fetch_patch, normalize_patch:
            wizard = self._open(
                "ext-20", "forward", to_emails="colleague@example.com", body=False
            )
            with self._mock_send_raw() as mocked:
                wizard.action_send()
        mocked.assert_called_once()

    def test_forward_reattaches_the_originals_files(self):
        # A forward that delivers your comment and none of the forwarded
        # email is not a forward.
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-21")
        with fetch_patch, normalize_patch:
            wizard = self._open(
                "ext-21", "forward", to_emails="colleague@example.com"
            )
            with self._mock_send_raw() as mocked:
                wizard.action_send()
        attachments = mocked.call_args.kwargs["attachments"]
        self.assertEqual([a["filename"] for a in attachments], ["spec.pdf"])
        self.assertEqual(attachments[0]["mimetype"], "application/pdf")
        self.assertTrue(attachments[0]["content"])

    def test_repeat_action_on_same_item_does_not_duplicate_conversation(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-9")
        with fetch_patch, normalize_patch:
            first = self._open(
                "ext-9", "reply", body="<p>First</p>", file_in_odoo=True
            )
            second = self._open(
                "ext-9", "reply", body="<p>Second</p>", file_in_odoo=True
            )
            with self._mock_send_raw():
                action1 = first.action_send()
                action2 = second.action_send()
        self.assertEqual(action1["res_id"], action2["res_id"])
