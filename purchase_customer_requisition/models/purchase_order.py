from datetime import datetime

from odoo import models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def action_merge(self):
        """Override to clear requisition_id before merging multiple POs, then
        consolidate the resulting lines for the same product regardless of their
        ``date_planned`` (core only merges lines whose dates are within 24h).
        """
        if len(self) > 1:
            # Check if all POs have the same requisition_id
            unique_requisitions = set(order.requisition_id.id for order in self if order.requisition_id)

            # Only clear requisition_ids if they are different
            if len(unique_requisitions) > 1:
                self.write({'requisition_id': False})

        result = super().action_merge()

        # Post-pass: consolidate same-product lines whose dates differ by >24h
        # (core's matcher requires dates within 24h; we relax only that clause).
        for order in self.filtered(lambda o: o.state in ('draft', 'sent')):
            order._consolidate_lines_ignoring_date()

        return result

    def _consolidate_lines_ignoring_date(self):
        """Merge this order's lines that match on core's matching tuple MINUS the
        24h date clause: (product_id, product_uom, product_packaging_id,
        product_packaging_qty, analytic_distribution, discount).

        For each group of >1 line: the earliest-dated line is the survivor; every
        other line is merged into it via ``_merge_po_line`` (which, through the
        ``purchase_stock`` override, also transfers ``move_dest_ids`` -- preserving
        the MTO/MPS procurement chain), the survivor's ``date_planned`` is set to
        the earliest date, then the non-survivor lines are unlinked.
        """
        self.ensure_one()
        _SENTINEL = datetime.max
        groups = {}
        for line in self.order_line:
            if line.display_type in ('line_note', 'line_section'):
                continue
            key = (
                line.product_id.id,
                line.product_uom.id,
                line.product_packaging_id.id,
                line.product_packaging_qty,
                tuple(sorted((line.analytic_distribution or {}).items())),
                line.discount,
            )
            groups.setdefault(key, self.env['purchase.order.line'])
            groups[key] += line

        for group in groups.values():
            if len(group) <= 1:
                continue
            # Capture the earliest date BEFORE merging: _merge_po_line bumps
            # product_qty, which is a dependency of the date_planned stored
            # compute, so reading date_planned afterwards would recompute it to
            # the seller-derived date and lose the earliest value.
            earliest = min(
                (l.date_planned for l in group if l.date_planned), default=False
            )
            survivor = min(group, key=lambda l: l.date_planned or _SENTINEL)
            for other in group - survivor:
                survivor._merge_po_line(other)
            if earliest:
                survivor.date_planned = earliest
            (group - survivor).unlink()
