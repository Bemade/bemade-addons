# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import fields, models

from .product_product import BOM_CHANGE_POLICY_PARAM, DEFAULT_BOM_CHANGE_POLICY


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bom_rule_change_policy = fields.Selection(
        selection=[
            ("overwrite", "Overwrite the existing bill of materials"),
            ("revision", "Create a new revision and retire the old one"),
        ],
        string="Generated BOM Changes",
        default=DEFAULT_BOM_CHANGE_POLICY,
        config_parameter=BOM_CHANGE_POLICY_PARAM,
        help="How regeneration treats a generated bill of materials that "
        "already exists. Overwrite keeps one record per variant and rewrites "
        "it, which is simplest but leaves no trace of what the bill of "
        "materials said before. Revision never rewrites: it produces a new "
        "bill of materials and archives the old one, so every version that "
        "was ever quoted or built from stays readable, at the cost of a "
        "growing history.",
    )
