# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

import keyword

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductAttributeValueParam(models.Model):
    _name = "product.attribute.value.param"
    _description = "Named numeric parameter of an attribute value"
    _order = "attribute_value_id, name"

    attribute_value_id = fields.Many2one(
        comodel_name="product.attribute.value",
        string="Attribute Value",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(
        string="Parameter",
        required=True,
        help="Identifier used in bill-of-materials quantity expressions, "
        "for example 'volume' or 'trains'.",
    )
    value = fields.Float(
        required=True,
        digits="Product Unit of Measure",
    )

    @api.constrains("name")
    def _check_name_is_identifier(self):
        """Parameter names are evaluated as variables, so they must be usable
        as such. Catching this at entry keeps expression evaluation from
        failing later with something far less intelligible."""
        for param in self:
            name = param.name or ""
            if not name.isidentifier() or keyword.iskeyword(name):
                raise ValidationError(
                    _(
                        "%(name)r is not a valid parameter name. Use a plain "
                        "identifier such as 'volume' or 'height_in'.",
                        name=name,
                    )
                )

    @api.constrains("name", "attribute_value_id")
    def _check_name_unique_per_value(self):
        for param in self:
            duplicate = self.search_count(
                [
                    ("attribute_value_id", "=", param.attribute_value_id.id),
                    ("name", "=", param.name),
                    ("id", "!=", param.id),
                ]
            )
            if duplicate:
                raise ValidationError(
                    _(
                        "Attribute value %(value)s already defines a "
                        "parameter named %(name)r.",
                        value=param.attribute_value_id.display_name,
                        name=param.name,
                    )
                )
