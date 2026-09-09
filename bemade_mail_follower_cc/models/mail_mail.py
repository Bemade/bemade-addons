# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class MailMail(models.Model):
    _inherit = "mail.mail"

    email_cc_display_only = fields.Char(
        "Cc (display only)",
        help="Followers shown in the Cc header. Not used for SMTP delivery.",
    )

    def _prepare_outgoing_list(self, mail_server=False, recipients_follower_status=None):
        res = super()._prepare_outgoing_list(
            mail_server=mail_server,
            recipients_follower_status=recipients_follower_status,
        )

        # Drop the stray "Undisclosed recipients" email.
        #
        # When a Cc is set on the mail (e.g. mail_composer_cc_bcc puts the
        # composer's manual Cc partners into mail.email_cc) but the mail has no
        # mail.email_to, core's _prepare_outgoing_list emits an extra entry with
        # an EMPTY To and only a Cc (see odoo commit 46bad8f0) — the email
        # client then renders "Undisclosed recipients" in the To field.
        # mail_composer_cc_bcc removes that entry, but only on the inline
        # composer send path (its pop is gated on the is_from_composer context),
        # so the stray entry survives whenever the mail is sent from the queue /
        # cron (a fresh mail.mail recordset where that context is gone).
        # Strip it here, but only when every Cc-only recipient already has its
        # own personalised To entry, so no recipient loses their delivery.
        # SMTP envelope recipients (RCPT TO) of the entries that DO have a To.
        deliver_to = set()
        for entry in res:
            if entry.get("email_to"):
                deliver_to.update(entry.get("email_to_normalized") or [])
        kept = []
        for entry in res:
            # The stray entry has no To header at all; its SMTP recipients live
            # in email_to_normalized (derived by core from mail.email_cc).
            if not entry.get("email_to"):
                stray_rcpts = set(entry.get("email_to_normalized") or [])
                if stray_rcpts and stray_rcpts <= deliver_to:
                    # Every recipient of this Cc-only entry already receives a
                    # personalised To email — the entry is redundant. Drop it so
                    # no "Undisclosed recipients" email goes out.
                    continue
            kept.append(entry)
        res = kept

        if not self.email_cc_display_only:
            return res

        cc_display = tools.mail.email_split_and_format_normalize(self.email_cc_display_only)
        if not cc_display:
            return res

        for entry in res:
            existing = set(entry.get("email_cc") or [])
            entry["email_cc"] = list(existing) + [e for e in cc_display if e not in existing]
            # Intentionally NOT adding to email_to_normalized to avoid SMTP delivery

        return res
