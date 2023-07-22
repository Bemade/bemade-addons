# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def create(self, vals):
        newemployee = super(HrEmployee, self).create(vals)
        pw_bundle = self.env['password.bundle'].create({
            'name': newemployee.name,
            'notes': f"Created new employee Password Bundle for {newemployee.name}"
        })
        self.env['password.access'].create({
            'bundle_id': pw_bundle.id,
            'user_id': newemployee.user_id.id,
            'access_level': 'full',
        })
        return newemployee