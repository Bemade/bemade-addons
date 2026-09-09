# Acceptance criteria (task #3965):
#   AC-7/AC-8 (test plan #3, load-bearing): quiet-capturing a stub into a
#     NEW conversation creates the conversation, adds From/To/Cc as
#     participants (not followers), posts an mt_note with transport_id
#     falsy + external_id set, maps the correspondent to the From partner
#     (not the acting user), and sends zero external emails.
#   AC-7 (test plan #4): capturing into an EXISTING conversation threads the
#     message and does not duplicate an already-present participant.
#   AC-6 (conversation_inbox's GTD actions rely on these idempotent-capture
#     primitives): _capture_or_find files a not-yet-seen external_id once,
#     and returns the SAME conversation (no duplicate filing) on a repeat
#     call for the same external_id -- so acting twice on one inbox item
#     (e.g. reply, then later reassign) never creates two conversations.

from unittest.mock import patch

from odoo.tests import TransactionCase


class TestConversationCapture(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conversation = cls.env["mail.conversation"]
        cls.Participant = cls.env["mail.conversation.participant"]
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Capture Transport"}
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Customer Corp", "email": "customer@example.com"}
        )

    def _stub(self, **overrides):
        stub = {
            "subject": "Need a quote",
            "body": "<p>Please send a quote.</p>",
            "email_from": "customer@example.com",
            "to": ["sales@example.com"],
            "cc": ["watcher@example.com"],
            "external_id": "ext-msg-1",
        }
        stub.update(overrides)
        return stub

    def _outgoing_mail_ids(self):
        return set(self.env["mail.mail"].search([]).ids)

    def test_capture_into_new_conversation(self):
        before_mail_ids = self._outgoing_mail_ids()

        conversation = self.Conversation._capture_stub(
            self.transport, self._stub(), mode="new"
        )

        self.assertTrue(conversation)
        self.assertEqual(conversation.name, "Need a quote")

        # participants, not followers
        self.assertFalse(conversation.message_follower_ids)
        emails = set(conversation.participant_ids.mapped("email_normalized"))
        self.assertEqual(
            emails, {"customer@example.com", "sales@example.com", "watcher@example.com"}
        )

        # correct-correspondent mapping: the From participant resolves to
        # the actual customer partner, not the capturing/admin user.
        requester = conversation.participant_ids.filtered(
            lambda p: p.email_normalized == "customer@example.com"
        )
        self.assertEqual(requester.partner_id, self.customer)
        self.assertEqual(requester.role, "requester")
        self.assertNotEqual(requester.partner_id, self.env.user.partner_id)

        # the posted message is an internal note carrying transport metadata
        messages = conversation.message_ids.filtered(lambda m: m.body)
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertEqual(message.subtype_id, self.env.ref("mail.mt_note"))
        # model contract: transport_id falsy => internal note. Quiet capture
        # deliberately leaves it falsy (the notify-safety guard this relies
        # on, per the task design's Risks section) -- provenance is instead
        # recorded on external_id (message) and primary_transport_id (conv).
        self.assertFalse(message.transport_id)
        self.assertEqual(conversation.primary_transport_id, self.transport)
        self.assertEqual(message.external_id, "ext-msg-1")

        # zero external emails produced
        self.assertEqual(self._outgoing_mail_ids(), before_mail_ids)

    def test_capture_into_existing_conversation_dedups_participants(self):
        conversation = self.Conversation._capture_stub(
            self.transport, self._stub(), mode="new"
        )
        initial_participant_count = len(conversation.participant_ids)
        initial_message_count = len(conversation.message_ids)
        before_mail_ids = self._outgoing_mail_ids()

        second_stub = self._stub(
            subject="Re: Need a quote",
            body="<p>Following up.</p>",
            external_id="ext-msg-2",
        )
        result = self.Conversation._capture_stub(
            self.transport, second_stub, mode="existing", target=conversation
        )

        self.assertEqual(result, conversation)
        self.assertEqual(
            len(conversation.participant_ids),
            initial_participant_count,
            "no duplicate participants on a follow-up capture",
        )
        self.assertEqual(
            len(conversation.message_ids), initial_message_count + 1
        )
        self.assertEqual(self._outgoing_mail_ids(), before_mail_ids)

    def test_capture_link_mode_links_record(self):
        record = self.env["res.partner"].create({"name": "Linked Record"})
        conversation = self.Conversation._capture_stub(
            self.transport, self._stub(), mode="link", target=record
        )
        self.assertEqual(len(conversation.link_ids), 1)
        link = conversation.link_ids
        self.assertEqual(link.res_model, "res.partner")
        self.assertEqual(link.res_id, record.id)

    def test_capture_or_find_is_idempotent(self):
        transport_model = type(self.transport)
        raw = {"external_id": "ext-idem-1"}
        with patch.object(
            transport_model, "_fetch", return_value=raw, autospec=True
        ), patch.object(
            transport_model,
            "_normalize",
            return_value=self._stub(external_id="ext-idem-1"),
            autospec=True,
        ):
            first = self.Conversation._capture_or_find(self.transport, "ext-idem-1")
            second = self.Conversation._capture_or_find(self.transport, "ext-idem-1")

        self.assertTrue(first)
        self.assertEqual(
            first,
            second,
            "a repeat GTD action on the same inbox item must not file a "
            "second conversation",
        )
        self.assertEqual(
            self.Conversation.search_count(
                [("participant_ids.email", "=", "customer@example.com")]
            ),
            1,
        )

    def test_find_captured_returns_empty_for_unknown_external_id(self):
        self.assertFalse(
            self.Conversation._find_captured(self.transport, "never-seen")
        )

    def test_find_captured_never_crosses_transport(self):
        other_transport = self.env["conversation.transport"].create(
            {"name": "Other Transport"}
        )
        self.Conversation._capture_stub(
            self.transport, self._stub(external_id="ext-cross-1"), mode="new"
        )
        self.assertFalse(
            self.Conversation._find_captured(other_transport, "ext-cross-1")
        )

    def test_all_participant_emails_reply_all_includes_cc(self):
        conversation = self.Conversation._capture_stub(
            self.transport, self._stub(), mode="new"
        )
        reply_only = conversation._all_participant_emails(roles=("to", "requester"))
        reply_all = conversation._all_participant_emails()
        self.assertNotIn("watcher@example.com", reply_only)
        self.assertIn("watcher@example.com", reply_all)
        self.assertIn("customer@example.com", reply_all)
