from odoo import fields, models, api


class FollowupLine(models.Model):
    _inherit = 'account_followup.followup.line'

    account_hold = fields.Boolean(string="Place on Credit Hold",
                                  help="Place clients on account hold, restricting confirmation of new orders.")
