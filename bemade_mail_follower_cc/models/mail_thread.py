# -*- coding: utf-8 -*-
from odoo import models, tools


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _notify_by_email_get_base_mail_values(self, message, additional_values=None):
        res = super()._notify_by_email_get_base_mail_values(
            message, additional_values=additional_values
        )
        if not message.model or not message.res_id:
            return res

        followers = self.env["mail.followers"].search([
            ("res_model", "=", message.model),
            ("res_id", "=", message.res_id),
        ])
        follower_partners = followers.mapped("partner_id").filtered("email")
        if not follower_partners:
            return res

        cc_display = ", ".join(
            tools.formataddr((p.name or "", p.email))
            for p in follower_partners
        )
        res["email_cc_display_only"] = cc_display
        return res
