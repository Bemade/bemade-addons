from odoo import models, fields, api, _

class FollowUpReport(models.AbstractModel):
    _inherit = 'account.followup.report'

    def _get_line_info(self, followup_line):
        res = super()._get_line_info(followup_line)
        res.update({'credit_hold': followup_line.account_hold})
        return res
    @api.model
    def credit_hold(self, options):
        partner_id = options['partner_id']
        partner = self.env['res.partner'].browse(partner_id)
        partner.action_credit_hold()
