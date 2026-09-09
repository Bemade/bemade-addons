# -*- coding: utf-8 -*-
# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Case 2 (task #3422): a composer send with a manual Cc must not produce a
stray "Undisclosed recipients" email (empty To header, only a Cc).

The defect only surfaces when the queued mail is actually delivered from the
queue / cron — a fresh ``mail.mail`` recordset on which the transient composer's
``is_from_composer`` context no longer exists, so ``mail_composer_cc_bcc`` skips
the de-duplication that removes core's Cc-only "Undisclosed recipients" entry
(core ``mail.mail._prepare_outgoing_list`` adds it because ``mail.email_cc`` is
set while ``mail.email_to`` is empty). These tests reproduce that delivery path
and assert the stray email is gone while every recipient is still delivered to.
"""
from odoo.addons.mail.tests.common import MailCommon, mail_new_test_user
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.tools.mail import email_normalize


@tagged("post_install", "-at_install", "bemade_mail_follower_cc")
class TestComposerCcNoStray(MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.composer_cc_installed = bool(
            cls.env["ir.module.module"].search([
                ("name", "=", "mail_composer_cc_bcc"),
                ("state", "=", "installed"),
            ])
        )
        cls.author = mail_new_test_user(
            cls.env, login="cc_author", name="Author",
            email="author@test.example.com",
            groups="base.group_user,base.group_partner_manager",
            notification_type="email",
        )
        # Two EXTERNAL followers (no user -> customer notification by email).
        cls.ext1 = cls.env["res.partner"].create({
            "name": "External One", "email": "ext1@customer.example.com",
        })
        cls.ext2 = cls.env["res.partner"].create({
            "name": "External Two", "email": "ext2@customer.example.com",
        })
        # The manually-added Cc partner (Marc's noilish@gmail.com analogue).
        cls.manual_cc = cls.env["res.partner"].create({
            "name": "Manual Cc", "email": "manualcc@external.example.com",
        })

    def _make_record(self):
        rec = self.env["res.partner"].create({
            "name": "Thread Record", "email": "thread@test.example.com",
        })
        rec.message_subscribe(partner_ids=[self.ext1.id, self.ext2.id])
        return rec

    def _deliver_from_queue(self, record, manual_cc=True):
        """Post via the composer, then deliver from a FRESH mail.mail recordset
        (the queue / cron path), capturing each outgoing email at build_email.
        Returns the list of captured outgoing emails for this message."""
        vals = {"body": "<p>Case test</p>", "subject": "CaseX"}
        if manual_cc:
            vals["partner_cc_ids"] = [(6, 0, [self.manual_cc.id])]
        composer = self.env["mail.compose.message"].with_user(self.author).with_context(
            default_model="res.partner",
            default_res_ids=record.ids,
            default_partner_ids=[(6, 0, [self.ext1.id, self.ext2.id])],
        ).create(vals)
        with self.mock_mail_gateway():
            composer._action_send_mail()
        mails = self.env["mail.mail"].sudo().search(
            [("mail_message_id", "in", record.message_ids.ids)]
        )
        self.assertTrue(mails, "no mail.mail created")
        # Re-queue and deliver from a fresh recordset -> drops the composer ctx,
        # exactly like the real outgoing-mail cron does.
        mails.write({"state": "outgoing"})
        fresh = self.env["mail.mail"].sudo().browse(mails.ids)
        with self.mock_mail_gateway():
            fresh.send()
            return list(self._mails)

    @mute_logger("odoo.addons.mail.models.mail_mail", "odoo.models.unlink")
    def test_no_undisclosed_email_on_queue_send(self):
        """No outgoing email may have an empty To header (Undisclosed recipients)."""
        if not self.composer_cc_installed:
            self.skipTest("mail_composer_cc_bcc not installed")

        sent = self._deliver_from_queue(self._make_record())
        self.assertTrue(sent, "no emails were sent")
        for mail in sent:
            self.assertTrue(
                mail.get("email_to"),
                "Stray 'Undisclosed recipients' email: an outgoing email has "
                "an empty To header. email_to=%r email_cc=%r"
                % (mail.get("email_to"), mail.get("email_cc")),
            )

    @mute_logger("odoo.addons.mail.models.mail_mail", "odoo.models.unlink")
    def test_all_recipients_still_delivered(self):
        """Stripping the stray entry must not lose the manual Cc recipient:
        the 2 externals AND the manual Cc partner each still get exactly one
        email addressed To them."""
        if not self.composer_cc_installed:
            self.skipTest("mail_composer_cc_bcc not installed")

        sent = self._deliver_from_queue(self._make_record())
        expected = {
            email_normalize(self.ext1.email),
            email_normalize(self.ext2.email),
            email_normalize(self.manual_cc.email),
        }
        delivered = set()
        for mail in sent:
            for addr in (mail.get("email_to") or []):
                n = email_normalize(addr)
                if n:
                    delivered.add(n)
        self.assertEqual(
            delivered, expected,
            "Every recipient (2 externals + manual Cc) must still receive a "
            "personalised email. delivered=%r" % (delivered,),
        )
        self.assertEqual(
            len(sent), len(expected),
            "Expected exactly one email per recipient (%d), got %d: %r"
            % (len(expected), len(sent),
               [(m.get("email_to"), m.get("email_cc")) for m in sent]),
        )

    @mute_logger("odoo.addons.mail.models.mail_mail", "odoo.models.unlink")
    def test_case1_followers_only_unaffected(self):
        """Case 1 (no manual composer Cc): no email_cc is set on the mail, so
        core never creates a Cc-only entry — the strip must be a no-op and each
        follower still gets exactly one personalised email."""
        if not self.composer_cc_installed:
            self.skipTest("mail_composer_cc_bcc not installed")

        sent = self._deliver_from_queue(self._make_record(), manual_cc=False)
        expected = {
            email_normalize(self.ext1.email),
            email_normalize(self.ext2.email),
        }
        delivered = set()
        for mail in sent:
            self.assertTrue(
                mail.get("email_to"),
                "Case 1 produced an empty-To email: %r" % (mail,),
            )
            for addr in (mail.get("email_to") or []):
                n = email_normalize(addr)
                if n:
                    delivered.add(n)
        self.assertEqual(delivered, expected)
