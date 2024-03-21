from odoo import models, fields, api


class HrPayrollStructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'

    default_pay_periods_per_year = fields.Integer(
        compute="_compute_pay_periods_per_year",
        compute_sudo=True,
    )

    @api.depends("default_schedule_pay")
    def _compute_pay_periods_per_year(self):
        pay_periods_map = {
            'annually': 1,
            'semi-annually': 2,
            'quarterly': 4,
            'bi-monthly': 6,
            'monthly': 12,
            'semi-monthly': 24,
            'bi-weekly': 26,
            'weekly': 52,
            'daily': 365,
        }
        for rec in self:
            rec.default_pay_periods_per_year = pay_periods_map.get(rec.default_schedule_pay, False)