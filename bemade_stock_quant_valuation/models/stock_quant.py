from odoo import models, fields, api


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    value_unit = fields.Float(related='product_id.standard_price', readonly=True,
                              groups='stock.group_stock_manager', digits='Product Price')
    value_difference = fields.Float(compute='_compute_difference_value',
                                    help='The value of the difference between the '
                                         'quantity on hand and the counted '
                                         'quantity.',
                                    groups='stock.group_stock_manager',
                                    digits='Product Price',
                                    store=True)

    @api.depends('inventory_diff_quantity', 'value_unit')
    def _compute_difference_value(self):
        for rec in self.filtered(lambda r: r.inventory_quantity is not None):
            rec.value_difference = rec.value_unit * rec.inventory_diff_quantity
