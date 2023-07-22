# -*- coding: utf-8 -*-

from odoo import models, fields, api


class password_bundle(models.Model):
    _inherit = 'password.bundle'
    _name = 'password.bundle'

    @api.model
    def _default_access_admin_ids(self):
        """
        Default method for access_ids
        """
        values = {
            'access_level': 'admin',
            'group_id': self.env.ref('base.group_system').id,
        }
        return [(0, 0, values)]

    # BV: UGLY HACK
    # I should be able to remove this field, but I can't just override the default function
    # _default_access_ids, so I rename it _default_access_admin_ids and override the th field

    access_ids = fields.One2many(
        "password.access",
        "bundle_id",
        default=_default_access_admin_ids,
    )

