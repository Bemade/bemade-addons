# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    bom_rule_bom_id = fields.Many2one(
        comodel_name="mrp.bom",
        string="Generated Bill of Materials",
        readonly=True,
        copy=False,
        index=True,
        help="The generated bill of materials this line was costed from. "
        "Recorded when the product was set, so the quotation keeps pointing "
        "at what it was priced from even after the rules move on.",
    )
    bom_rule_message = fields.Text(
        string="BOM Generation Message",
        readonly=True,
        copy=False,
        help="Why generation could not produce a bill of materials for this "
        "line's configuration.",
    )
    bom_rule_state = fields.Selection(
        selection=[
            ("none", "Not rule-generated"),
            ("generated", "Generated"),
            ("superseded", "Superseded"),
            ("refused", "Refused"),
        ],
        string="BOM Status",
        compute="_compute_bom_rule_state",
        help="What stands behind this line's cost.",
    )
    # A fourth state, "costed from estimated prices", might look like it belongs here
    # too, but it can only be derived from the cost-confidence signal that
    # ``mrp_bom_variant_rule`` exposes on the generated bill of materials.
    # It is deliberately left out rather than reimplemented locally: this
    # module adds no capability the core does not already publish.

    bom_rule_cost_confidence = fields.Selection(
        related="bom_rule_bom_id.cost_confidence",
        string="Cost Basis",
        readonly=True,
        help="How far the cost behind this line can be relied on. Firm means "
        "every component of its bill of materials had a current vendor "
        "price; Estimated means at least one did not, and the figure carries "
        "that much less weight.\n\n"
        "Relayed from the bill of materials, which decides it; this module "
        "does not assess prices itself.",
    )
    # Confidence is deliberately NOT folded into bom_rule_state. Whether the
    # bill of materials is the current one and whether its component prices
    # are fresh are independent questions, and a single selection could only
    # answer one of them at a time.

    @api.depends("bom_rule_bom_id", "bom_rule_bom_id.active", "bom_rule_message")
    def _compute_bom_rule_state(self):
        # Read plainly, without sudo. A sales user can read mrp.bom, and
        # test_salesperson_without_mrp_rights_can_read_state guards that. If
        # a deployment ever tightens those rights the test fails loudly,
        # which is the outcome we want: a defensive sudo here would hide the
        # access problem instead of surfacing it.
        for line in self:
            bom = line.bom_rule_bom_id
            if not bom:
                # A refusal is only meaningful while nothing was produced; a
                # later successful generation clears the message with it.
                line.bom_rule_state = (
                    "refused" if line.bom_rule_message else "none"
                )
            elif not bom.active:
                # Archived means a regeneration elsewhere replaced it. The
                # quotation was costed from this revision all the same.
                line.bom_rule_state = "superseded"
            else:
                line.bom_rule_state = "generated"

    def _bom_rule_apply(self, force=False):
        """Generate the line's bill of materials and record it on the line.

        Called only from write paths. Generation is a deliberate act of
        configuring a line, never a side effect of reading or pricing one.

        A refusal is recorded rather than raised: the rule table having a
        hole is not a reason to stop someone from editing a quotation.
        """
        for line in self:
            if line.display_type or not line.product_id:
                continue
            try:
                # Generating is an internal consequence of configuring a
                # quotation line, not the salesperson operating on the
                # manufacturing model. Requiring them to hold create rights
                # on mrp.bom would put the capability out of reach of exactly
                # the people the module exists to serve.
                bom = line.product_id.sudo()._bom_rule_generate(force=force)
            except UserError as err:
                line.bom_rule_bom_id = False
                line.bom_rule_message = str(err)
                continue
            line.bom_rule_bom_id = bom.id
            line.bom_rule_message = False

    def action_bom_rule_regenerate(self):
        """Regenerate control on the order line.

        Returns nothing so the salesperson stays on the quotation: the point
        of the control is to fix the line in place after a ruleset
        correction, not to navigate to the bill of materials.
        """
        self._bom_rule_apply(force=True)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._bom_rule_apply()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if "product_id" in vals:
            self._bom_rule_apply()
        return res
