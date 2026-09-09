# Copyright (C) 2024 Bemade Inc. (<https://www.bemade.org>).
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
from odoo import api, models

# Map Many2one field name → partner_address_ranking context value
_RANKING_FIELDS = {
    "partner_invoice_id": "invoice",
    "partner_shipping_id": "delivery",
}


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        """Inject 'partner_address_ranking' into address field context strings.

        After super() has fully combined the arch (all inheriting views applied),
        we textually merge the ranking key into the existing context attribute of
        partner_invoice_id and partner_shipping_id field nodes.  This preserves
        every other key already present — especially 'show_address' set by a
        consuming module — instead of wholesale-replacing the context dict.

        Injection is:
        * Idempotent: skipped when the key is already present.
        * Textual: avoids ast.literal_eval because the context string may contain
          the bare name ``partner_id`` (not a valid Python literal).
        * Safe for the groups-hidden duplicate partner_invoice_id node (line 795
          in the base view): injecting the key harmlessly on all matched nodes is
          fine — the hidden node simply carries an unused ranking key.
        """
        arch, view = super()._get_view(view_id=view_id, view_type=view_type, **options)
        if view_type != "form":
            return arch, view

        for field_name, ranking_type in _RANKING_FIELDS.items():
            for node in arch.xpath(f"//field[@name='{field_name}']"):
                ctx = node.get("context", "")
                if "partner_address_ranking" in ctx:
                    # Already injected (idempotent guard)
                    continue
                if ctx.strip().startswith("{") and ctx.strip().endswith("}"):
                    # Merge into existing dict: insert after the opening brace
                    opening = ctx.index("{")
                    merged = (
                        ctx[: opening + 1]
                        + f"'partner_address_ranking': '{ranking_type}', "
                        + ctx[opening + 1 :]
                    )
                else:
                    # No context attribute or unexpected shape — set a fresh dict
                    merged = f"{{'partner_address_ranking': '{ranking_type}'}}"
                node.set("context", merged)

        return arch, view

    @api.depends("partner_id")
    def _compute_partner_invoice_id(self):
        for order in self:
            if not order.partner_id:
                order.partner_invoice_id = False
                continue
            ranked = order.partner_id._get_ranked_address_ids("invoice")
            order.partner_invoice_id = ranked[0] if ranked else False

    @api.depends("partner_id")
    def _compute_partner_shipping_id(self):
        for order in self:
            if not order.partner_id:
                order.partner_shipping_id = False
                continue
            ranked = order.partner_id._get_ranked_address_ids("delivery")
            order.partner_shipping_id = ranked[0] if ranked else False

    def write(self, vals):
        res = super().write(vals)
        # Invalidate the per-cursor ranking cache whenever SO confirmation
        # state or address fields change, so subsequent calls re-compute.
        if vals.keys() & {"state", "partner_invoice_id", "partner_shipping_id"}:
            self.mapped("partner_id")._invalidate_ranking_cache()
        return res
