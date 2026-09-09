# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install")
class TestForward(TransactionCase):
    """Test the real outbound Forward action (task 3965).

    Forward must be a genuine outbound send (a `mail.mail` through the
    configured transport) with correct From/Reply-To/threading -- not just an
    internal reassignment. See the "Forwarding decision" section of the
    design for why this matters.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, mail_create_nolog=True))

        cls.lost_parent = cls.env["lost.message.parent"].search([], limit=1)
        if not cls.lost_parent:
            cls.lost_parent = cls.env["lost.message.parent"].create({})

        # Authorized From address, distinct from the original sender: this is
        # the anti-spoof guarantee the design mandates.
        cls.from_address = cls.env["mail.from.address"].create(
            {
                "name": "Bemade Triage",
                "email": "triage@bemade.org",
            }
        )

    def _create_lost_message(self, subject=None, body=None, message_id=None, **kwargs):
        """Helper to create a lost message with a unique subject/body so
        mail_loop_prevention / dedup logic never blocks creation."""
        import time

        unique_id = str(time.time_ns())[-8:]
        if subject is None:
            subject = f"Test forward {unique_id}"
        if body is None:
            body = f"Test forward body {unique_id}"
        if message_id is None:
            message_id = f"<orig-{unique_id}@example.com>"

        with mute_logger("odoo.addons.mail_loop_prevention.models.mail_thread"):
            message = self.env["mail.thread"]._create_lost_message(
                body=body,
                body_is_html=False,
                subject=subject,
                model="lost.message.parent",
                res_id=self.lost_parent.id,
                email_from="external.customer@example.com",
            )
        # _create_lost_message doesn't take message_id directly; set it so we
        # can assert on threading headers.
        message.write({"message_id": message_id})
        return message

    def test_forward_envelope_is_correct_and_not_spoofed(self):
        """Forwarding sends exactly one real mail.mail with the correct,
        non-spoofed envelope."""
        message = self._create_lost_message(subject="Invoice #123")

        mail_domain = [("email_to", "=", "ext@example.com")]
        before = self.env["mail.mail"].search_count(mail_domain)

        mail = message._do_forward("ext@example.com", from_address=self.from_address)

        after = self.env["mail.mail"].search_count(mail_domain)
        self.assertEqual(after, before + 1, "Exactly one mail.mail should be created")
        self.assertIn("ext@example.com", mail.email_to)
        self.assertTrue(mail.subject.startswith("Fwd:"))
        self.assertEqual(mail.email_from, self.from_address.email)
        self.assertNotEqual(
            mail.email_from, message.email_from,
            "From must never be the spoofed original external sender",
        )
        self.assertEqual(mail.reply_to, self.from_address.email)

    def test_forward_preserves_threading_headers(self):
        """The outgoing mail carries References/In-Reply-To pointing at the
        original message's Message-Id."""
        message = self._create_lost_message(message_id="<original-thread@example.com>")

        mail = message._do_forward("ext@example.com", from_address=self.from_address)

        self.assertIn("<original-thread@example.com>", mail.references or "")
        self.assertIn("In-Reply-To", mail.headers or "")
        self.assertIn("<original-thread@example.com>", mail.headers or "")

    def test_forward_copies_attachments_when_enabled(self):
        """copy_attachments=True links the original's attachment(s) to the
        outgoing mail."""
        message = self._create_lost_message()
        attachment = self.env["ir.attachment"].create(
            {
                "name": "invoice.pdf",
                "datas": b"ZmFrZSBwZGYgY29udGVudA==",
                "res_model": "mail.message",
                "res_id": message.id,
            }
        )
        message.write({"attachment_ids": [(4, attachment.id)]})

        mail = message._do_forward(
            "ext@example.com", from_address=self.from_address, copy_attachments=True
        )

        self.assertIn(attachment.id, mail.attachment_ids.ids)

    def test_forward_skips_attachments_when_disabled(self):
        """copy_attachments=False does not link the original's attachments."""
        message = self._create_lost_message()
        attachment = self.env["ir.attachment"].create(
            {
                "name": "invoice.pdf",
                "datas": b"ZmFrZSBwZGYgY29udGVudA==",
                "res_model": "mail.message",
                "res_id": message.id,
            }
        )
        message.write({"attachment_ids": [(4, attachment.id)]})

        mail = message._do_forward(
            "ext@example.com", from_address=self.from_address, copy_attachments=False
        )

        self.assertNotIn(attachment.id, mail.attachment_ids.ids)

    def test_forward_marks_original_handled_and_audited(self):
        """After forward, the source message is categorized "Forwarded" and
        lost_comments records the actor and recipient."""
        message = self._create_lost_message()

        message._do_forward("ext@example.com", from_address=self.from_address)

        forwarded_subcat = self.env.ref("mail_manual_routing_ux.subcategory_forwarded")
        self.assertEqual(message.lost_subcategory_id, forwarded_subcat)
        self.assertIn("Forwarded to ext@example.com", message.lost_comments or "")
        self.assertIn(self.env.user.name, message.lost_comments or "")

    def test_forward_empty_recipient_raises_and_creates_no_mail(self):
        """Calling send with a blank email_to raises UserError and creates no
        mail.mail."""
        message = self._create_lost_message()
        before = self.env["mail.mail"].search_count([])

        with self.assertRaises(UserError):
            message._do_forward("", from_address=self.from_address)

        after = self.env["mail.mail"].search_count([])
        self.assertEqual(before, after)

    def test_forward_wizard_action_forward(self):
        """The Forward wizard drives _do_forward for every selected message."""
        message = self._create_lost_message()

        wizard = self.env["mail.forward.wizard"].create(
            {
                "message_ids": [(6, 0, [message.id])],
                "email_to": "ext@example.com",
                "from_address_id": self.from_address.id,
            }
        )
        result = wizard.action_forward()

        self.assertEqual(result["type"], "ir.actions.act_window_close")
        forwarded_subcat = self.env.ref("mail_manual_routing_ux.subcategory_forwarded")
        self.assertEqual(message.lost_subcategory_id, forwarded_subcat)

    def test_action_forward_returns_wizard(self):
        """mail.message.action_forward opens the Forward wizard."""
        message = self._create_lost_message()

        action = message.action_forward()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "mail.forward.wizard")

    def test_finance_triage_forward_delegates_to_do_forward(self):
        """Regression: driving the finance triage wizard with
        action='forward' now produces an outbound mail with corrected
        From/Reply-To/References (proves the refactor routes through
        _do_forward), and the message ends up in the Finance subcategory."""
        message = self._create_lost_message(message_id="<finance-orig@example.com>")

        mail_domain = [("email_to", "=", "finance@example.com")]
        before = self.env["mail.mail"].search_count(mail_domain)

        wizard = self.env["mail.finance.triage.wizard"].create(
            {
                "message_ids": [(6, 0, [message.id])],
                "action": "forward",
                "forward_email": "finance@example.com",
            }
        )
        wizard.action_triage()

        after = self.env["mail.mail"].search_count(mail_domain)
        self.assertEqual(after, before + 1)
        mail = self.env["mail.mail"].search(mail_domain, order="id desc", limit=1)
        self.assertNotEqual(mail.email_from, message.email_from)
        self.assertTrue(mail.reply_to)
        self.assertIn("<finance-orig@example.com>", mail.references or "")

        finance_subcat = self.env.ref(
            "mail_manual_routing_ux.subcategory_finance", raise_if_not_found=False
        )
        if finance_subcat:
            self.assertEqual(message.lost_subcategory_id, finance_subcat)
