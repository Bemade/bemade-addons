# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import api, fields, models


class MrpBomRuleSet(models.Model):
    _name = "mrp.bom.rule.set"
    _description = "BOM generation ruleset"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    product_tmpl_ids = fields.Many2many(
        comodel_name="product.template",
        string="Product Templates",
        help="Templates whose variants this ruleset builds bills of "
        "materials for.",
    )
    slot_ids = fields.One2many(
        comodel_name="mrp.bom.slot",
        inverse_name="rule_set_id",
        string="Slots",
    )
    rule_ids = fields.One2many(
        comodel_name="mrp.bom.rule",
        inverse_name="rule_set_id",
        string="Rules",
    )
    revision = fields.Integer(
        default=1,
        readonly=True,
        copy=False,
        help="Bumped whenever the rules change. Generated bills of materials "
        "record the revision that produced them.",
    )

    def _bump_revision(self):
        for rule_set in self:
            rule_set.revision = rule_set.revision + 1

    @api.model
    def _for_product(self, product):
        """The active ruleset bound to this variant's template, if any."""
        return self.search(
            [("product_tmpl_ids", "in", product.product_tmpl_id.ids)],
            limit=1,
        )
