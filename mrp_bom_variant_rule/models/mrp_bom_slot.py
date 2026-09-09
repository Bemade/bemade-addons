# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import api, fields, models


class MrpBomSlot(models.Model):
    _name = "mrp.bom.slot"
    _description = "Component slot of a BOM ruleset"
    _order = "rule_set_id, sequence, id"

    rule_set_id = fields.Many2one(
        comodel_name="mrp.bom.rule.set",
        string="Ruleset",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    required = fields.Boolean(
        default=True,
        help="A required slot that matches no rule refuses generation "
        "outright. Clear this for slots a configuration may legitimately "
        "leave empty.",
    )
    rule_ids = fields.One2many(
        comodel_name="mrp.bom.rule",
        inverse_name="slot_id",
        string="Rules",
    )
    rule_count = fields.Integer(
        string="Rules",
        compute="_compute_rule_count",
        help="How many rules compete for this slot. Only the first one that "
        "matches a given variant contributes a line.",
    )

    @api.depends("rule_ids")
    def _compute_rule_count(self):
        for slot in self:
            slot.rule_count = len(slot.rule_ids)

    @api.depends("name", "rule_set_id.name")
    def _compute_display_name(self):
        """Slot names such as "Vessel" repeat across rulesets, so a bare name
        in a many2one is ambiguous the moment there is more than one ruleset."""
        for slot in self:
            slot.display_name = " / ".join(
                part for part in (slot.rule_set_id.name, slot.name) if part
            )

    @api.model_create_multi
    def create(self, vals_list):
        slots = super().create(vals_list)
        slots.rule_set_id._bump_revision()
        return slots

    def write(self, vals):
        rule_sets = self.rule_set_id
        result = super().write(vals)
        (rule_sets | self.rule_set_id)._bump_revision()
        return result

    def unlink(self):
        rule_sets = self.rule_set_id
        result = super().unlink()
        rule_sets.exists()._bump_revision()
        return result
