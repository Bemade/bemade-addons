# Acceptance criteria (task #3965):
#   AC-6/AC-9 (test plan #6, outbound _send): action_reply calls
#     transport._send with the explicit recipient list, records the
#     outbound mail.message with transport_id + external_id, and the
#     pipeline emails no external participant directly (delivery is the
#     transport's job, never Odoo's notification pipeline -- the
#     notification-safety invariant).
#   GTD action set (AC6): action_forward sends to an arbitrary address
#     (not necessarily an existing participant); action_reassign hands the
#     conversation to a user/team; action_archive marks it done.

from unittest.mock import patch

from odoo.tests import TransactionCase


class TestConversationActions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conversation = cls.env["mail.conversation"]
        cls.sendable_transport = cls.env["conversation.transport"].create(
            {"name": "Sendable Transport", "sendable": True}
        )
        cls.non_sendable_transport = cls.env["conversation.transport"].create(
            {"name": "Read Only Transport", "sendable": False}
        )
        cls.conversation = cls.Conversation.create(
            {
                "name": "Action Conversation",
                "primary_transport_id": cls.sendable_transport.id,
            }
        )

    def _outgoing_mail_ids(self):
        return set(self.env["mail.mail"].search([]).ids)

    def test_action_reply_calls_transport_send_with_explicit_recipients(self):
        before_mail_ids = self._outgoing_mail_ids()
        transport_model = type(self.sendable_transport)
        with patch.object(
            transport_model, "_send", return_value="sent-ext-id-1", autospec=True
        ) as mocked_send:
            message = self.conversation.action_reply(
                "<p>Here is the answer</p>",
                recipients=["customer@example.com"],
            )

        mocked_send.assert_called_once()
        _self, conversation_arg, message_arg = mocked_send.call_args.args[:3]
        kwargs = mocked_send.call_args.kwargs
        self.assertEqual(conversation_arg, self.conversation)
        self.assertEqual(message_arg, message)
        self.assertEqual(kwargs.get("recipients"), ["customer@example.com"])

        self.assertEqual(message.transport_id, self.sendable_transport)
        self.assertEqual(message.external_id, "sent-ext-id-1")
        self.assertEqual(message.subtype_id, self.env.ref("mail.mt_comment"))

        # delivery is entirely the transport's job -- the notification
        # pipeline must not have produced any mail.mail of its own.
        self.assertEqual(self._outgoing_mail_ids(), before_mail_ids)

    def test_action_reply_requires_sendable_transport(self):
        from odoo.exceptions import UserError

        conversation = self.Conversation.create(
            {
                "name": "No Transport Conversation",
                "primary_transport_id": self.non_sendable_transport.id,
            }
        )
        with self.assertRaises(UserError):
            conversation.action_reply("<p>Hi</p>")

    def test_action_forward_sends_to_arbitrary_address(self):
        transport_model = type(self.sendable_transport)
        with patch.object(
            transport_model, "_send", return_value="fwd-ext-id-1", autospec=True
        ) as mocked_send:
            message = self.conversation.action_forward(
                "<p>FYI</p>", "not-a-participant@example.com"
            )

        mocked_send.assert_called_once()
        kwargs = mocked_send.call_args.kwargs
        self.assertEqual(kwargs.get("recipients"), ["not-a-participant@example.com"])
        self.assertEqual(message.transport_id, self.sendable_transport)

    def test_action_reassign(self):
        team = self.env["mail.conversation.team"].create({"name": "Reassign Team"})
        other_user = self.env["res.users"].create(
            {
                "name": "Other User",
                "login": "other_user_test@example.com",
                "email": "other_user_test@example.com",
            }
        )
        self.conversation.action_reassign(user=other_user, team=team)
        self.assertEqual(self.conversation.user_id, other_user)
        self.assertEqual(self.conversation.team_id, team)

    def test_action_archive_marks_done(self):
        self.assertEqual(self.conversation.state, "open")
        self.conversation.action_archive()
        self.assertEqual(self.conversation.state, "done")
