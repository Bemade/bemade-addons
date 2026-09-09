# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import api, fields, models

from .product_product import AUTO_APPLY_PARAM, ECO_TYPE_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    bom_rule_eco_type_id = fields.Many2one(
        comodel_name="mrp.eco.type",
        string="Rule Revision ECO Type",
        config_parameter=ECO_TYPE_PARAM,
        help="The engineering change order type that revisions of a "
        "generated bill of materials are filed under. Defaults to the "
        "standard BOM Updates type.",
    )
    bom_rule_eco_auto_apply = fields.Boolean(
        string="Apply Rule Revisions Immediately",
        default=True,
        help="Apply the engineering change order as soon as it is created, "
        "so the regenerated bill of materials becomes the active one at "
        "once. Turn this off to have every rule-driven revision reviewed: "
        "the change order is filed for approval and the previous bill of "
        "materials stays active, and stays what quotations are costed from, "
        "until somebody approves it.",
    )

    # A boolean held in ir.config_parameter cannot simply be declared with
    # ``config_parameter``: set_param deletes a parameter whose value is
    # falsy, so storing False would remove the key and send the next read
    # back to the default of True. Storing the two states as explicit
    # strings is what makes "off" persist.

    @api.model
    def get_values(self):
        values = super().get_values()
        values["bom_rule_eco_auto_apply"] = self.env[
            "product.product"
        ]._bom_rule_eco_auto_apply()
        return values

    def set_values(self):
        res = super().set_values()
        self.env["ir.config_parameter"].sudo().set_param(
            AUTO_APPLY_PARAM, "1" if self.bom_rule_eco_auto_apply else "0"
        )
        return res
