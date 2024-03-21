from odoo import models, fields, api, _
from odoo.tools.float_utils import float_is_zero, float_compare


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    margin_actual = fields.Monetary("Our Margin", compute='_compute_margin_actual', store=False)

    margin_percent_actual = fields.Float(
        string='Our Margin (%)',
        compute='_compute_margin_actual',
        store=False,
        group_operator='avg'
    )

    @api.depends('order_line.margin_actual', 'amount_untaxed')
    def _compute_margin_actual(self):
        for order in self:
            order.margin_actual = sum(order.order_line.mapped('margin_actual'))
            order.margin_percent_actual = order.amount_untaxed and order.margin_actual / order.amount_untaxed


