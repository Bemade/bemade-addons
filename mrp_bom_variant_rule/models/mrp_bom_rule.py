# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools.expression import check_expression, evaluate_expression


class MrpBomRule(models.Model):
    _name = "mrp.bom.rule"
    _description = "BOM generation rule"
    _order = "slot_id, sequence, id"

    rule_set_id = fields.Many2one(
        comodel_name="mrp.bom.rule.set",
        string="Ruleset",
        related="slot_id.rule_set_id",
        store=True,
        index=True,
    )
    slot_id = fields.Many2one(
        comodel_name="mrp.bom.slot",
        string="Slot",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    condition_ids = fields.One2many(
        comodel_name="mrp.bom.rule.condition",
        inverse_name="rule_id",
        string="Conditions",
        help="All conditions must hold for the rule to match. A rule with no "
        "conditions matches every variant and is therefore a catch-all.",
    )
    selection_mode = fields.Selection(
        selection=[
            ("fixed", "One component"),
            ("mapped", "Looked up from an attribute"),
            ("none", "Deliberately nothing"),
        ],
        string="Component is",
        required=True,
        default="fixed",
        help="A rule usually names one component. When a slot takes a "
        "different component for each value of an attribute -- a tank per "
        "tank size, say -- a mapping expresses that as one rule with a table "
        "instead of one rule per component, so adding a size is a row rather "
        "than a rule.\n\n"
        "'Deliberately nothing' is for what a variant does not include: a "
        "system whose valve the customer supplies, say. It satisfies its slot "
        "without contributing a component, which is different from a slot "
        "nobody has answered yet -- that one refuses and says so.",
    )
    mapping_attribute_id = fields.Many2one(
        comodel_name="product.attribute",
        string="Looked Up From",
        ondelete="restrict",
        help="The attribute whose value chooses the component.",
    )
    mapping_ids = fields.One2many(
        comodel_name="mrp.bom.rule.mapping",
        inverse_name="rule_id",
        string="Component Table",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Component",
        ondelete="restrict",
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit of Measure",
        help="Defaults to the component's own unit of measure.",
    )
    qty_expr = fields.Char(
        string="Quantity",
        required=True,
        default="1",
        help="Arithmetic over the variant's named parameters, "
        "for example 'volume * 1.2 * trains'.",
    )
    mapping_summary = fields.Char(
        string="Mapped",
        compute="_compute_mapping_summary",
        help="How many attribute values the table covers, so a gap is "
        "visible without opening it.",
    )
    condition_summary = fields.Char(
        string="Applies When",
        compute="_compute_condition_summary",
        help="The rule's conditions in one line, so a reader can scan a "
        "slot's rules top to bottom and see which variant each one claims "
        "without opening every row.",
    )

    @api.depends("condition_ids.attribute_id", "condition_ids.value_ids")
    def _compute_condition_summary(self):
        for rule in self:
            clauses = [
                "%s: %s"
                % (
                    condition.attribute_id.name or "",
                    ", ".join(condition.value_ids.mapped("name")),
                )
                for condition in rule.condition_ids
            ]
            # A rule with no conditions is a catch-all, and saying so plainly
            # matters more than an empty cell: it is the row that silently
            # shadows everything sequenced after it.
            rule.condition_summary = " and ".join(clauses) or _(
                "Any variant (catch-all)"
            )

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        rules.rule_set_id._bump_revision()
        return rules

    def write(self, vals):
        # The ruleset the rule belonged to before the write has also changed
        # shape, so both sides of a re-parenting move.
        rule_sets = self.rule_set_id
        result = super().write(vals)
        (rule_sets | self.rule_set_id)._bump_revision()
        return result

    def unlink(self):
        rule_sets = self.rule_set_id
        result = super().unlink()
        rule_sets.exists()._bump_revision()
        return result

    @api.constrains("qty_expr")
    def _check_qty_expr(self):
        for rule in self:
            try:
                check_expression(rule.qty_expr)
            except ValueError as err:
                raise ValidationError(
                    _(
                        "Quantity expression %(expr)r is not a valid "
                        "arithmetic expression: %(reason)s",
                        expr=rule.qty_expr,
                        reason=str(err),
                    )
                ) from err

    def _matches(self, variant):
        """True when every condition of this rule holds for the variant."""
        self.ensure_one()
        values = variant.product_template_attribute_value_ids.mapped(
            "product_attribute_value_id"
        )
        return all(
            condition._holds(values) for condition in self.condition_ids
        )

    def _compute_qty(self, params):
        """Quantity this rule contributes, given the variant's parameters."""
        self.ensure_one()
        return evaluate_expression(self.qty_expr, params)

    @api.depends("selection_mode", "mapping_ids", "mapping_attribute_id")
    def _compute_mapping_summary(self):
        for rule in self:
            if rule.selection_mode != "mapped":
                rule.mapping_summary = False
                continue
            covered = len(rule.mapping_ids)
            total = len(rule.mapping_attribute_id.value_ids)
            rule.mapping_summary = _(
                "%(covered)s of %(total)s values", covered=covered, total=total
            )

    @api.constrains("selection_mode", "product_id", "mapping_attribute_id")
    def _check_component_is_determined(self):
        """Whichever mode a rule is in, it must be able to name a component.

        Checked rather than left to fail at generation: a rule that cannot
        produce anything is a slot that refuses, and the author should learn
        that while writing the rule, not when a quotation will not price.
        """
        for rule in self:
            if rule.selection_mode == "none":
                continue
            if rule.selection_mode == "fixed" and not rule.product_id:
                raise ValidationError(
                    _("Rule %s names no component.", rule.display_name)
                )
            if rule.selection_mode == "mapped" and not rule.mapping_attribute_id:
                raise ValidationError(
                    _(
                        "Rule %s looks its component up from an attribute, but "
                        "no attribute is set.",
                        rule.display_name,
                    )
                )

    def _bom_rule_gap(self, values):
        """Name the empty cell, when this rule declined for want of a row.

        A blank cell is a legitimate state: there are combinations Durpro has
        never sold and has no wish to invent a product for. What must not
        happen is that the blank goes unnamed -- "no rule matches" makes
        someone open every rule in the slot, whereas naming the attribute and
        the value is a question answerable in one edit.
        """
        self.ensure_one()
        if self.selection_mode != "mapped" or not self.mapping_attribute_id:
            return ""
        selected = values.filtered(
            lambda v: v.attribute_id == self.mapping_attribute_id
        )
        if not selected:
            return _(
                "%(attribute)s (the variant sets no value for it)",
                attribute=self.mapping_attribute_id.display_name,
            )
        return _(
            "%(attribute)s = %(value)s",
            attribute=self.mapping_attribute_id.display_name,
            value=", ".join(selected.mapped("name")),
        )

    def _bom_rule_component(self, values):
        """The component this rule contributes for ``values``, or an empty set.

        ``values`` is the variant's ``product.attribute.value`` records. A
        mapped rule with no row for the selected value contributes nothing,
        which the caller treats exactly as an unmatched rule: the slot stays
        unfilled and says so, rather than falling back to something plausible.
        """
        self.ensure_one()
        if self.selection_mode == "none":
            # Answered, and the answer is nothing. The caller distinguishes
            # this from an empty result by the flag, because "supplies nothing"
            # and "nobody has decided" must not look alike.
            return self.env["product.product"], self.env["uom.uom"]
        if self.selection_mode == "fixed":
            return self.product_id, self.product_uom_id
        selected = values.filtered(
            lambda v: v.attribute_id == self.mapping_attribute_id
        )
        mapping = self.mapping_ids.filtered(
            lambda m: m.attribute_value_id in selected
        )[:1]
        if not mapping:
            return self.env["product.product"], self.env["uom.uom"]
        return mapping.product_id, mapping.product_uom_id

    def _bom_rule_supplies_nothing(self, values):
        """Whether this rule positively answers "nothing" for ``values``."""
        self.ensure_one()
        if self.selection_mode == "none":
            return True
        if self.selection_mode != "mapped":
            return False
        selected = values.filtered(
            lambda v: v.attribute_id == self.mapping_attribute_id
        )
        row = self.mapping_ids.filtered(
            lambda m: m.attribute_value_id in selected
        )[:1]
        return bool(row) and row.supplies_nothing


class MrpBomRuleCondition(models.Model):
    _name = "mrp.bom.rule.condition"
    _description = "Attribute condition of a BOM generation rule"
    _order = "rule_id, id"

    rule_id = fields.Many2one(
        comodel_name="mrp.bom.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    attribute_id = fields.Many2one(
        comodel_name="product.attribute",
        string="Attribute",
        required=True,
        ondelete="cascade",
    )
    value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        string="Values",
        required=True,
        help="The condition holds when the variant carries any one of these "
        "values for the attribute.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        conditions = super().create(vals_list)
        conditions.rule_id.rule_set_id._bump_revision()
        return conditions

    def write(self, vals):
        result = super().write(vals)
        self.rule_id.rule_set_id._bump_revision()
        return result

    def unlink(self):
        rule_sets = self.rule_id.rule_set_id
        result = super().unlink()
        rule_sets.exists()._bump_revision()
        return result

    def _holds(self, variant_values):
        """A disjunction within one attribute: the variant's value for this
        attribute must be among those listed."""
        self.ensure_one()
        return bool(self.value_ids & variant_values)
