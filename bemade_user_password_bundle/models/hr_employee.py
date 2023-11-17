# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model_create_multi
    def create(self, vals_list):
        new_employees = super().create(vals_list)
        for newemployee in new_employees:
            pw_bundle = self.env['password.bundle'].create({
                'name': newemployee.name,
                'notes': f"Created new employee Password Bundle for {newemployee.name}"
            })
            self.env['password.access'].create({
                'bundle_id': pw_bundle.id,
                'user_id': newemployee.user_id.id,
                'access_level': 'full',
            })
        return new_employees