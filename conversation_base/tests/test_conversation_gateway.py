# Acceptance criteria (task #3965):
#   AC-9 (test plan #5, gateway backbone): inbound mail to a mail.conversation
#     alias creates a conversation with participants-not-followers via
#     message_new; a follow-up whose References match threads into the SAME
#     conversation (no second conversation created). Correlation stays
#     within a transport (auto-correlation by References/In-Reply-To for
#     email); the base mail.thread gateway machinery provides the threading,
#     our message_new override only adds participant hygiene on top.

from odoo.addons.mail.tests.common import MailCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestConversationGateway(MailCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conversation_model = cls.env["ir.model"]._get("mail.conversation")
        cls.alias = cls.env["mail.alias"].create(
            {
                "alias_name": "conv-inbox-test",
                "alias_model_id": conversation_model.id,
                "alias_domain_id": cls.mail_alias_domain.id,
            }
        )
        cls.alias_email = "%s@%s" % (cls.alias.alias_name, cls.mail_alias_domain.name)

    def _inbound(self, msg_id, in_reply_to=None, to=None):
        headers = (
            "MIME-Version: 1.0\n"
            "Date: Thu, 27 Dec 2018 16:27:45 +0100\n"
            "Message-ID: %s\n"
            "Subject: Question about my order\n"
            "From: Gateway Customer <gateway_customer@example.com>\n"
            "To: %s\n"
            "Cc: watcher@example.com\n"
        ) % (msg_id, to or self.alias_email)
        if in_reply_to:
            headers += "In-Reply-To: %s\n" % in_reply_to
        mime = (
            headers
            + 'Content-Type: text/plain; charset="UTF-8"\n'
            + "\n"
            + "Hello, I have a question.\n"
        )
        return self.env["mail.thread"].sudo().message_process(False, mime)

    def test_inbound_creates_conversation_with_participants_not_followers(self):
        conversation_id = self._inbound("<gw-msg-1@example.com>")
        conversation = self.env["mail.conversation"].browse(conversation_id)

        self.assertTrue(conversation)
        self.assertFalse(conversation.message_follower_ids)

        emails = set(conversation.participant_ids.mapped("email_normalized"))
        self.assertIn("gateway_customer@example.com", emails)
        self.assertIn("watcher@example.com", emails)

        requester = conversation.participant_ids.filtered(
            lambda p: p.email_normalized == "gateway_customer@example.com"
        )
        self.assertEqual(requester.role, "requester")

    def test_reply_with_matching_references_threads_into_same_conversation(self):
        before_count = self.env["mail.conversation"].search_count([])

        conversation_id = self._inbound("<gw-msg-2@example.com>")
        self.assertTrue(conversation_id)
        self.assertEqual(
            self.env["mail.conversation"].search_count([]), before_count + 1
        )

        # a follow-up In-Reply-To the first message must NOT create a
        # second conversation.
        second_id = self._inbound(
            "<gw-msg-2-reply@example.com>", in_reply_to="<gw-msg-2@example.com>"
        )
        self.assertEqual(
            second_id,
            conversation_id,
            "a reply matching In-Reply-To should thread into the same "
            "conversation, not create a second one",
        )
        self.assertEqual(
            self.env["mail.conversation"].search_count([]),
            before_count + 1,
            "no second conversation created for a correlated reply",
        )
