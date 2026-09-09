# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MrpBomRuleMapping(models.Model):
    _name = "mrp.bom.rule.mapping"
    _description = "Bill of materials rule mapping entry"
    _order = "sequence, id"

    rule_id = fields.Many2one(
        comodel_name="mrp.bom.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    attribute_value_id = fields.Many2one(
        comodel_name="product.attribute.value",
        string="When the value is",
        required=True,
        ondelete="cascade",
    )
    supplies_nothing = fields.Boolean(
        string="Supplies Nothing",
        help="Tick for a value that deliberately contributes no component -- a "
        "system whose control valve the customer supplies, for instance. This "
        "is an answer, and the slot is satisfied by it. A row left out of the "
        "table altogether is a question, and refuses.",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Use this component",
        ondelete="restrict",
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit",
        help="Leave empty to use the component's own unit of measure.",
    )

    _sql_constraints = [
        (
            "value_unique_per_rule",
            "unique(rule_id, attribute_value_id)",
            "A mapping may give each attribute value only one component.",
        ),
    ]

    # attribute_value_id is in the trigger list because it is always present
    # on create, whereas a row that names neither a component nor "supplies
    # nothing" mentions neither of those fields -- and so would never be
    # validated, which is exactly the row this check exists to catch.
    @api.constrains("product_id", "supplies_nothing", "attribute_value_id")
    def _check_row_says_something(self):
        for mapping in self:
            if mapping.supplies_nothing and mapping.product_id:
                raise ValidationError(
                    _(
                        "%(value)s both names a component and says it supplies "
                        "nothing. It has to be one or the other.",
                        value=mapping.attribute_value_id.display_name,
                    )
                )
            if not mapping.supplies_nothing and not mapping.product_id:
                raise ValidationError(
                    _(
                        "%(value)s names no component. Leave the row out "
                        "entirely to mean the question is open, or tick "
                        "'Supplies Nothing' to mean the answer is none.",
                        value=mapping.attribute_value_id.display_name,
                    )
                )

    @api.constrains("attribute_value_id", "rule_id")
    def _check_value_belongs_to_the_mapped_attribute(self):
        """A row keyed on the wrong attribute can never match.

        It is not harmless: the table looks complete, and the slot silently
        stops resolving for the value someone thought they had covered.
        """
        for mapping in self:
            attribute = mapping.rule_id.mapping_attribute_id
            if attribute and mapping.attribute_value_id.attribute_id != attribute:
                raise ValidationError(
                    _(
                        "%(value)s belongs to %(its_attribute)s, but this rule "
                        "maps on %(mapped)s. A row keyed on another attribute "
                        "can never match.",
                        value=mapping.attribute_value_id.display_name,
                        its_attribute=mapping.attribute_value_id.attribute_id.display_name,
                        mapped=attribute.display_name,
                    )
                )
