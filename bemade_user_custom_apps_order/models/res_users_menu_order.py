# Copyright (C) 2023 Bemade.org
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# Import the required classes and decorators from Odoo
from odoo import models, fields, api

class ResUsersMenuOrder(models.Model):
    """
    This model represents the preferred order in which a user wants to see their apps.
    Each record represents the order of one app for one user.
    """

    _name = 'res.users.menu.order'
    _description = 'User Menu Order'

    user_id = fields.Many2one('res.users', string='User', required=True, )
    # The user who has set a preferred order for their apps.

    menu_id = fields.Many2one('ir.ui.menu', string='Menu', required=True)
    # The app that the user has set a preferred order for.

    sequence = fields.Integer(string='Sequence')
    # The order of the app. A lower sequence means the app will appear earlier.

    _sql_constraints = [
        ('user_menu_uniq', 'unique(user_id, menu_id)', 'A user should only have one order record per menu!'),
    ]

