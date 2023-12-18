from odoo import fields, models, api, _
from datetime import date


class Partner(models.Model):
    _inherit = 'res.partner'

    postpone_hold_until = fields.Date(string="Postpone Hold",
                                      help="Grace period specific to this partner despite unpaid invoices.", )

    hold_bg = fields.Boolean(string="Hold (technical)",
                             compute="_compute_hold_bg",
                             store=True,
                             default=False)
    on_hold = fields.Boolean(string="Account on Hold",
                             help="Client account is on hold for unpaid overdue invoices.",
                             compute="_compute_on_hold")

    @api.depends('postpone_hold_until', 'hold_bg')
    def _compute_on_hold(self):
        # manually re-compute hold_bg since followup_status doesn't get updated in Python but gets recalculated
        # by an SQL query every time
        self._compute_hold_bg()
        for rec in self:
            if rec.hold_bg and not (rec.postpone_hold_until and rec.postpone_hold_until > date.today()):
                rec.on_hold = True
            else:
                if rec.on_hold:
                    rec.message_post(_("Credit hold lifted."))
                rec.on_hold = False

    @api.autovacuum
    def _cleanup_expired_hold_postponements(self):
        expired_holds = self.search([('postpone_hold_until', '<=', date.today())])
        expired_holds.write({'postpone_hold_until': False})

    def action_credit_hold(self):
        for rec in self:
            rec.hold_bg = True
            rec.message_post(body=_('Placed on credit hold.'))

    def action_lift_credit_hold(self):
        for rec in self:
            rec.hold_bg = False
            rec.message_post(body=_('Credit hold lifted.'))

    def _execute_followup_partner(self):
        res = super()._execute_followup_partner()
        if self.followup_status == 'in_need_of_action':
            if self.followup_line_id.account_hold:
                self.action_credit_hold()
        return res

    @api.depends('followup_status', 'followup_line_id')
    def _compute_hold_bg(self):
        first_followup_level = self._get_first_followup_level()
        for rec in self:
            prev_hold_bg = rec.hold_bg
            level = rec.followup_line_id
            if rec.followup_status == 'no_action_needed' and level == first_followup_level:
                rec.hold_bg = False
            else:
                rec.hold_bg = prev_hold_bg
