# Copyright (C) 2023 Bemade.org
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, api, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    # Define the One2many field for the app order records
    app_order_ids = fields.One2many(
        'res.users.menu.order', 'user_id', string='App Order Records')

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['app_order_ids']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['app_order_ids']

    @api.model
    def create(self, vals):
        """
        Overridden to create a new app order record for each top-level menu for the new user when a new user is created.
        """
        # Create the user
        new_user = super().create(vals)

        # Create a new app order record for each top-level menu for the new user
        menus = self.env['ir.ui.menu'].search([('parent_id', '=', False)])
        for menu in menus:
            self.env['res.users.menu.order'].create({
                'user_id': new_user.id,
                'menu_id': menu.id,
                'sequence': 9999,  # Or some other default sequence
            })

        return new_user

    def unlink(self):
        """
        Overridden to delete the app order records for the user being deleted when a user is deleted.
        """
        # Delete the app order records for the user being deleted
        self.env['res.users.menu.order'].search([('user_id', 'in', self.ids)]).unlink()

        # Delete the user
        return super().unlink()

    def write(self, vals):
        """
        Overridden to allow users to modify their own 'app_order_ids' field.
        """
        if 'app_order_ids' in vals and self.env.uid == self.id:
            # may be called with sudo can be replaced with WRITINGFIELDRIGHTS but works for now
            super(ResUsers, self.sudo()).write(vals)
        else:
            super().write(vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
