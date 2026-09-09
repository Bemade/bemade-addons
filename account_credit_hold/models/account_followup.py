from odoo import fields, models, api


class FollowupLine(models.Model):
    _inherit = "account_followup.followup.line"

    account_hold = fields.Boolean(
        string="Place on Credit Hold",
        help="Place clients on account hold, restricting confirmation of new orders.",
    )
    attach_credit_hold_report = fields.Boolean(
        string="Attach Credit Hold Report",
        help="DEPRECATED: PDF is now automatically sent with ALL followup emails for customers on credit hold.",
        default=False,
        invisible=True,
    )
