from odoo import models, fields, api, _


class GLSCanadaShippingEstimate(models.Model):
    _name = 'gls.canada.shipping.estimate'
    _description = 'GLS Canada Shipping Estimate'

    account_id = fields.Many2one('gls.canada.account', string='GLS Canada Account')
    total_charge = fields.Monetary()
    sale_order_id = fields.Many2one('sale.order', string='Sales Order')

    def set_service(self):
        self.ensure_one()
        carrier = self.sale_order_id.carrier_id
        self.sale_order_id._remove_delivery_line()
        self.sale_order_id.gls_canada_shipping_charge_id = self.id
        self.sale_order_id.set_delivery_line(carrier, self.total_charge)

class GLSCanadaRate(models.Model):
    _name = 'gls.canada.rate'
    _rec_name = 'rate_type'
