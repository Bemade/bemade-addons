# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    from_address_ids = fields.Many2many(
        "mail.from.address",
        "mail_from_address_user_rel",
        "user_id",
        "address_id",
        string="Allowed From Addresses",
        help="Email addresses this user can use as From address in mail composer",
    )