# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Construction helpers shared by the rule-engine test files.

Building a ruleset by hand takes four nested creates, which buries the point
of a test under scaffolding. These keep the tests readable by naming only what
each one actually varies.
"""

from odoo import Command


class RuleSetBuilderMixin:
    def _component(self, name, uom=None):
        return self.env["product.product"].create(
            {
                "name": name,
                "type": "consu",
                **({"uom_id": uom.id, "uom_po_id": uom.id} if uom else {}),
            }
        )

    def _rule_set(self, name="Ruleset", templates=None):
        if templates is None:
            templates = self.template
        return self.env["mrp.bom.rule.set"].create(
            {
                "name": name,
                "product_tmpl_ids": [Command.set(templates.ids)],
            }
        )

    def _slot(self, rule_set, name, sequence=10, required=True):
        return self.env["mrp.bom.slot"].create(
            {
                "rule_set_id": rule_set.id,
                "name": name,
                "sequence": sequence,
                "required": required,
            }
        )

    def _rule(
        self,
        slot,
        product,
        qty_expr="1",
        sequence=10,
        conditions=(),
        uom=None,
    ):
        """``conditions`` is a sequence of ``(attribute, values)`` pairs."""
        return self.env["mrp.bom.rule"].create(
            {
                "slot_id": slot.id,
                "sequence": sequence,
                "product_id": product.id,
                "qty_expr": qty_expr,
                "product_uom_id": uom.id if uom else False,
                "condition_ids": [
                    Command.create(
                        {
                            "attribute_id": attribute.id,
                            "value_ids": [Command.set(values.ids)],
                        }
                    )
                    for attribute, values in conditions
                ],
            }
        )
