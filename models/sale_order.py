from odoo import models, fields, api, _, Command


class SaleOrder(models.Model):
    _inherit = 'sale.order'

