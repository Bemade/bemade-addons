# Copyright (C) 2023 Bemade.org
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# Import the models package so Odoo knows to load our models
from . import models

# Import the Environment for creating an environment for superuser
# Import SUPERUSER_ID for using as the user id for the superuser
from odoo.api import Environment, SUPERUSER_ID

# This is the function that gets called after the module installation
def post_init_hook(cr, registry):
    # Create an environment with the database cursor and SUPERUSER_ID
    env = Environment(cr, SUPERUSER_ID, {})

    menus = env['ir.ui.menu'].search([('parent_id', '=', False)])

    # For each user in the system,
    for user in env['res.users'].search([]):
        # Iterate over each sequence
        for menu in menus:
            # Create a new record in 'res.users.menu.order' with the user, menu and sequence
            env['res.users.menu.order'].create({
                'user_id': user.id,
                'menu_id': menu.id
            })

