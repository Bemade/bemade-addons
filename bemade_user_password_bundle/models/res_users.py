# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def create(self, vals):
        newuser = super(ResUsers, self).create(vals)
        if vals.get("sel_groups_1_9_10", 9) == 1:
            pw_bundle = self.env['password.bundle'].create({
                'name': newuser.name,
            })
            self.env['password.access'].create({
                'bundle_id': pw_bundle.id,
                'user_id': newuser.id,
                'access_level': 'full'
            })

        return newuser

