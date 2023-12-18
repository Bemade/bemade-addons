from odoo import fields, models, api


class ModelName(models.Model):
    _inherit = "stock.picking"

    client_on_hold = fields.Boolean(string='Client on Hold',
                                    help="Whether or not a client has been put on hold due to unpaid invoices.",
                                    related="partner_id.on_hold")
