# Copyright (C) 2023 Bemade.org
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# Import the required classes and decorators from Odoo
from odoo import api, models

class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model_create_multi
    def create(self, vals_list):
        # Override the create method to handle new top-level menus
        records = super(IrUiMenu, self).create(vals_list)

        menus = self.env['ir.ui.menu'].search([('parent_id', '=', False)])

        # For each new menu
        for record in records:
            # If the menu is a top-level menu
            if not record.parent_id and record.id in menus.ids:
                # Create a 'res.users.menu.order' record for each user
                for user in self.env['res.users'].search([]):
                    self.env['res.users.menu.order'].create({
                        'user_id': user.id,
                        'menu_id': record.id,
                        'sequence': record.sequence,
                    })
        return records

    def unlink(self):
        # Override the unlink method to delete associated 'res.users.menu.order' records
        self.env['res.users.menu.order'].search([
            ('menu_id', 'in', self.ids)
        ]).unlink()
        return super(IrUiMenu, self).unlink()

    def write(self, vals):
        # Call the super method to perform the default write operation
        res = super(IrUiMenu, self).write(vals)

        menus = self.env['ir.ui.menu'].search([('parent_id', '=', False)])

        for self_record in self:
            if 'parent_id' in vals:
                if vals.get('parent_id') == False and self_record in menus:
                    # If the menu becomes a top-level menu, create a 'res.users.menu.order' record for each user
                    users = self.env['res.users'].search([])
                    for user in users:
                        existing_order = self.env['res.users.menu.order'].search([
                            ('user_id', '=', user.id),
                            ('menu_id', '=', self_record.id),
                        ], limit=1)
                        if not existing_order:
                            self.env['res.users.menu.order'].create({
                                'user_id': user.id,
                                'menu_id': self_record.id,
                                'sequence': self_record.sequence,
                            })
                else:
                    # Delete the corresponding 'res.users.menu.order' records
                    self.env['res.users.menu.order'].search([('menu_id', '=', self_record.id)]).unlink()
        return res

    def load_menus(self, debug):
        menus = super().load_menus(debug)

        # Retrieve the user's menu order records
        menu_order_records = self.env['res.users.menu.order'].search([('user_id', '=', self.env.uid)])

        # Create a dictionary that maps app ids to sequences
        sequence_dict = {record.menu_id.id: record.sequence for record in menu_order_records}

        # Retrieve the menu records for the IDs in menus['root']['children']
        menu_records = self.browse(menus['root']['children'])

        # Sort the menu records based on the sequences in the dictionary
        sorted_menu_records = menu_records.sorted(key=lambda menu: sequence_dict.get(menu.id, 9999))

        # Replace menus['root']['children'] with the IDs of the sorted menu records
        menus['root']['children'] = sorted_menu_records.ids

        return menus