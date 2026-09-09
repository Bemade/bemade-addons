# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import time

from odoo.addons.mail.tests.common import MailCommon
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

MAIL_TEMPLATE = """\
Return-Path: <{return_path}>
To: {to}
From: {email_from}
Subject: {subject}
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Date: Fri, 10 Aug 2012 14:16:26 +0000
Message-ID: {msg_id}
{extra}
Please call me as soon as possible this afternoon!
"""


@tagged("post_install", "-at_install", "mail_loop_prevention")
class TestMailLoopPrevention(MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        # Ensure module is enabled with defaults
        cls.ICP.set_param("mail_loop_prevention.enabled", "True")
        cls.ICP.set_param("mail_loop_prevention.block_auto_generated", "False")

    def _make_msg_dict(self, auto_submitted='', **kwargs):
        """Build a minimal msg_dict for _detect_loop_headers tests."""
        msg_dict = {
            'message_id': '<test@localhost>',
            'email_from': 'sender@example.com',
            'to': 'recipient@example.com',
            'references': '',
            'in_reply_to': '',
            'auto_submitted': auto_submitted,
        }
        msg_dict.update(kwargs)
        return msg_dict

    # ------------------------------------------------------------------
    # Unit tests — _detect_loop_headers
    # ------------------------------------------------------------------

    def test_auto_replied_dropped(self):
        """auto-replied emails are dropped."""
        msg_dict = self._make_msg_dict(auto_submitted='auto-replied')
        self.assertTrue(
            self.env['mail.thread']._detect_loop_headers(msg_dict),
        )

    def test_auto_generated_allowed_by_default(self):
        """auto-generated emails are allowed by default."""
        msg_dict = self._make_msg_dict(auto_submitted='auto-generated')
        self.assertFalse(
            self.env['mail.thread']._detect_loop_headers(msg_dict),
        )

    def test_auto_generated_blocked_when_configured(self):
        """auto-generated emails are blocked when the setting is enabled."""
        self.ICP.set_param(
            "mail_loop_prevention.block_auto_generated", "True"
        )
        msg_dict = self._make_msg_dict(auto_submitted='auto-generated')
        self.assertTrue(
            self.env['mail.thread']._detect_loop_headers(msg_dict),
        )

    def test_auto_submitted_no_allowed(self):
        """Auto-Submitted: no means human-sent — always allowed."""
        msg_dict = self._make_msg_dict(auto_submitted='no')
        self.assertFalse(
            self.env['mail.thread']._detect_loop_headers(msg_dict),
        )

    def test_missing_header_allowed(self):
        """Missing Auto-Submitted header — always allowed."""
        msg_dict = self._make_msg_dict(auto_submitted='')
        self.assertFalse(
            self.env['mail.thread']._detect_loop_headers(msg_dict),
        )

    def test_auto_submitted_with_parameters(self):
        """RFC 3834 semicolon parameters are stripped during message_parse."""
        import email as email_lib
        raw = (
            "From: sender@example.com\r\n"
            "To: recipient@example.com\r\n"
            "Subject: OOF\r\n"
            "Message-ID: <params-test@localhost>\r\n"
            "Auto-Submitted: auto-replied; owner-email=\"user@example.com\"\r\n"
            "\r\n"
            "Out of office.\r\n"
        )
        message = email_lib.message_from_bytes(
            raw.encode(), policy=email_lib.policy.SMTP
        )
        msg_dict = self.env['mail.thread'].message_parse(message)
        self.assertEqual(msg_dict['auto_submitted'], 'auto-replied')

    def test_module_disabled(self):
        """When the module is disabled, even auto-replied is allowed."""
        self.ICP.set_param("mail_loop_prevention.enabled", "False")
        msg_dict = self._make_msg_dict(auto_submitted='auto-replied')
        self.assertFalse(
            self.env['mail.thread']._detect_loop_headers(msg_dict),
        )

    def test_bounce_detection_still_works(self):
        """Odoo's built-in bounce-loop detection via References still works."""
        msg_dict = self._make_msg_dict(
            references='<abc-loop-detection-bounce-email@odoo.com>',
        )
        self.assertTrue(
            self.env['mail.thread']._detect_loop_headers(msg_dict),
        )

    # ------------------------------------------------------------------
    # Integration test — full gateway path via message_process
    # ------------------------------------------------------------------

    @mute_logger('odoo.addons.mail.models.mail_thread')
    def test_gateway_integration_auto_replied(self):
        """Full gateway: an email with Auto-Submitted: auto-replied is
        silently dropped before routing — no mail.message is created."""
        msg_id = "<%.7f-test-loop@iron.sky>" % time.time()
        alias_domain = self.alias_domain.strip() if hasattr(self, 'alias_domain') else 'test.mycompany.com'
        raw_email = MAIL_TEMPLATE.format(
            return_path='sender@example.com',
            to='catchall.test@%s' % alias_domain,
            email_from='sender@example.com',
            subject='OOF auto-reply test',
            msg_id=msg_id,
            extra='Auto-Submitted: auto-replied\n',
        )
        # Count messages before
        before = self.env['mail.message'].search_count(
            [('message_id', '=', msg_id)]
        )
        result = self.env['mail.thread'].message_process(None, raw_email)
        after = self.env['mail.message'].search_count(
            [('message_id', '=', msg_id)]
        )
        self.assertIsNone(result)
        self.assertEqual(before, after, "No mail.message should be created")
