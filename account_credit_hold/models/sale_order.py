from odoo import fields, models, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    client_on_hold = fields.Boolean(string='Client on Hold',
                                    help="Whether or not a client has been put on hold due to unpaid invoices.",
                                    related="partner_id.on_hold")

    @api.depends('client_on_hold')
    def action_confirm(self):
        if any(self.mapped('client_on_hold')):
            raise UserError(_("This client is on credit hold. No new orders can be confirmed until past-due invoices "
                              "are paid or the accounting team postpones the hold."))
        super().action_confirm()
