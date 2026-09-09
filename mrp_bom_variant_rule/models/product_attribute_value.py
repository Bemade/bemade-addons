# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import _, api, fields, models


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    param_ids = fields.One2many(
        comodel_name="product.attribute.value.param",
        inverse_name="attribute_value_id",
        string="Parameters",
        help="Named numbers this value contributes to bill-of-materials "
        "quantity expressions.",
    )

    param_summary = fields.Char(
        string="Parameters",
        compute="_compute_param_summary",
        help="The value's parameters in one line, so a rule author can see "
        "at a glance which names a quantity expression may reference.",
    )

    @api.depends("param_ids.name", "param_ids.value")
    def _compute_param_summary(self):
        for value in self:
            value.param_summary = ", ".join(
                "%s = %g" % (param.name or "", param.value)
                for param in value.param_ids
            )

    def action_bom_rule_open_params(self):
        """Open this value on its own so its parameters can be edited.

        The attribute form lists values in an inline editable list, which has
        no room for a nested one2many. A dialog on the value itself is the
        only place the parameters can actually be maintained next to the
        values they belong to.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Parameters of %s", self.display_name),
            "res_model": "product.attribute.value",
            "res_id": self.id,
            "view_mode": "form",
            "views": [
                (
                    self.env.ref(
                        "mrp_bom_variant_rule."
                        "view_product_attribute_value_form"
                    ).id,
                    "form",
                )
            ],
            "target": "new",
        }
