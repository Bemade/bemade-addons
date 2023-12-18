from odoo import models, fields, api, _


class FollowUpReport(models.AbstractModel):
    _inherit = 'account.followup.report'

    def _get_line_info(self, followup_line):
        res = super()._get_line_info(followup_line)
        res.update({
            'credit_hold': followup_line.account_hold
        })
        return res
