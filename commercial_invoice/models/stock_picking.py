# License: LGPL-3
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
from odoo import _, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_create_commercial_invoice(self):
        """Create a commercial invoice from the selected deliveries.

        Ported from ``verajet_commercial_invoice`` (task 3705 MR-1).  Backs the
        multi-select "Create CI from Deliveries" server action.
        """
        outgoing = self.filtered(lambda p: p.picking_type_id.code == "outgoing")
        if not outgoing:
            raise UserError(
                _("Commercial invoices can only be created from customer deliveries.")
            )
        ci = self.env["commercial.invoice"].create_from_pickings(outgoing)
        return {
            "type": "ir.actions.act_window",
            "name": _("Commercial Invoice"),
            "res_model": "commercial.invoice",
            "view_mode": "form",
            "res_id": ci.id,
            "target": "current",
        }
