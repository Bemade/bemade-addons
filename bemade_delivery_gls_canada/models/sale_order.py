from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    gls_canada_shipping_estimate_ids = fields.One2many('gls.canada.shipping.estimate', 'sale_order_id',
                                                       string='GLS Canada Rates')
    gls_canada_shipping_estimate_id = fields.Many2one('gls.canada.shipping.estimate', string='Shipping Estimate')
    delivery_billing_account = fields.Many2one('gls.canada.account', string='Delivery Billing Account')
