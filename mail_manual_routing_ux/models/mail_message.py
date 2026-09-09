# -*- coding: utf-8 -*-
from datetime import datetime

from markupsafe import Markup

from odoo import Command, _, fields, models
from odoo.exceptions import UserError


class MailMessage(models.Model):
    """Extend mail.message with subcategory and batch actions."""
    _inherit = 'mail.message'

    lost_subcategory_id = fields.Many2one(
        'lost.message.subcategory',
        string="Subcategory",
        help="Classification of this lost message.",
    )

    def write(self, vals):
        """Log subcategory changes into lost_comments as a simple audit trail."""
        if 'lost_subcategory_id' not in vals:
            return super().write(vals)

        # Capture old subcategory names before writing
        old_subcats = {
            rec.id: rec.lost_subcategory_id.name or 'None'
            for rec in self
        }

        result = super().write(vals)

        # Build log entry for each record that changed
        user_name = self.env.user.name
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        for rec in self:
            new_name = rec.lost_subcategory_id.name or 'None'
            old_name = old_subcats[rec.id]
            if old_name != new_name:
                entry = f"[{timestamp}] {user_name}: Subcategory: {old_name} → {new_name}"
                existing = rec.lost_comments or ''
                # Use super().write() to avoid recursion
                super(MailMessage, rec).write({
                    'lost_comments': (existing + '\n' + entry).strip()
                })
        return result

    def action_categorize(self):
        """Open wizard to categorize selected messages."""
        return {
            'name': 'Categorize Messages',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.message.categorize.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_message_ids': [(6, 0, self.ids)]},
        }

    def action_batch_delete(self):
        """Open wizard to confirm batch deletion."""
        return {
            'name': 'Delete Messages',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.message.delete.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_message_ids': [(6, 0, self.ids)]},
        }

    def action_notify_invalid_address(self):
        """Open wizard to notify sender of invalid address."""
        self.ensure_one()
        return {
            'name': 'Notify Invalid Address',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.invalid.address.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_message_id': self.id},
        }

    def action_finance_triage(self):
        """Open wizard for finance message triage."""
        return {
            'name': 'Finance Triage',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.finance.triage.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_message_ids': [(6, 0, self.ids)]},
        }

    def action_forward(self):
        """Open the Forward wizard: real outbound send, distinct from the
        silent internal Assign/Reassign routing (task 3965)."""
        return {
            'name': 'Forward',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.forward.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_message_ids': [(6, 0, self.ids)]},
        }

    def _do_forward(self, email_to, from_address=None, note=None,
                     copy_attachments=True, mark_forwarded=True):
        """Compose and send a real outbound "Fwd:" email for ``self``.

        Single source of truth for outbound forwarding, used by both the
        Forward wizard and (via delegation) the finance triage wizard. Fixes
        the correctness gaps of the ad-hoc sends that used to live in each
        wizard: proper **From** (an authorized team address, never the
        spoofed original sender -- avoids DMARC/SPF failure), proper
        **Reply-To** (routes replies back into triage) and proper
        **threading** (References/In-Reply-To set to the original
        Message-Id).

        :param str email_to: comma-separated recipient address(es).
        :param mail.from.address from_address: authorized From address to
            send as; falls back to the company/catchall address when not
            given.
        :param str note: optional HTML preface prepended above the quoted
            original message.
        :param bool copy_attachments: link the original message's
            attachments to the outgoing mail.
        :param bool mark_forwarded: set lost_subcategory_id to "Forwarded".
            Callers that apply their own subcategory afterwards (e.g. the
            finance triage wizard) pass False to avoid a spurious
            intermediate state.
        :return: the created ``mail.mail`` record.
        """
        self.ensure_one()
        if not email_to or not email_to.strip():
            raise UserError(_("Please enter at least one recipient to forward to."))

        from_email = from_address.email if from_address else False
        if not from_email:
            from_email = self.env.company.catchall_email or self.env.company.email
        if not from_email:
            raise UserError(_(
                "No authorized From address is configured. Configure one under "
                "the From Addresses settings, or set a company email."
            ))

        subject = self.subject or _("No subject")
        if not subject.lower().startswith(('fwd:', 'fw:')):
            subject = f"Fwd: {subject}"

        original_from = self.email_from or (
            self.author_id.display_name if self.author_id else _("Unknown sender")
        )
        quoted_header = Markup(
            "<p>---------- Forwarded message ----------<br/>"
            "From: %s<br/>Date: %s<br/>Subject: %s</p>"
        ) % (original_from, self.date or '', self.subject or '')
        original_body = Markup(self.body) if self.body else Markup('')
        body_html = quoted_header + original_body
        if note:
            note_html = note if isinstance(note, Markup) else Markup(note)
            body_html = note_html + body_html

        mail_vals = {
            'subject': subject,
            'body_html': body_html,
            'email_to': email_to,
            'email_from': from_email,
            'reply_to': from_email,
            # Deliberately NOT auto_delete: unlike the prior-art wizards this
            # replaces, a Forward should leave a durable, inspectable
            # mail.mail record (Settings > Technical > Email) -- it is a
            # genuine outbound send and the closest thing to a "Sent" trail
            # in this triage surface.
        }
        if self.message_id:
            mail_vals['references'] = self.message_id
            mail_vals['headers'] = repr({'In-Reply-To': self.message_id})
        if copy_attachments and self.attachment_ids:
            mail_vals['attachment_ids'] = [Command.set(self.attachment_ids.ids)]

        mail = self.env['mail.mail'].create(mail_vals)
        mail.send()

        if mark_forwarded:
            subcategory = self.env.ref(
                'mail_manual_routing_ux.subcategory_forwarded', raise_if_not_found=False)
            if subcategory:
                self.write({'lost_subcategory_id': subcategory.id})

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        entry = f"[{timestamp}] {self.env.user.name}: Forwarded to {email_to}"
        existing = self.lost_comments or ''
        self.write({'lost_comments': (existing + '\n' + entry).strip()})

        if self.model and self.res_id and self.model in self.env:
            record = self.env[self.model].browse(self.res_id)
            if record.exists() and hasattr(record, 'message_post'):
                record.message_post(
                    body=_(
                        "Forwarded to %(recipient)s by %(user)s.",
                        recipient=email_to, user=self.env.user.name,
                    ),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )

        return mail
