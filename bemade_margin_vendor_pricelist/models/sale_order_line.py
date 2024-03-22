from odoo import models, fields, api, _
from odoo.tools.float_utils import float_is_zero, float_compare


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    purchase_price_vendor = fields.Float(
        compute='_compute_purchase_price_vendor',
        string="Vendor Price",
        groups="base.group_user",
        digits='Product Price'
    )

    margin_percent_vendor = fields.Float(
        string='Margin (%) on Vendor Price',
        groups='base.group_user',
        group_operator='avg',
        compute='_compute_margin_vendor'
    )

    margin_vendor = fields.Float(
        string='Margin on Vendor Price',
        groups='base.group_user',
        digits='Product Price',
        compute='_compute_margin_vendor'
    )

    purchase_price_actual = fields.Float(
        compute="_compute_actual_margins",
        digits='Product Price',
        groups="base.group_user",
        string="Purchase Price"
    )

    margin_actual = fields.Float(
        compute="_compute_actual_margins",
        digits='Product Price',
        groups="base.group_user",
        string="Our Margin"
    )

    margin_percent_actual = fields.Float(
        compute="_compute_actual_margins",
        groups="base.group_user",
        string="Our Margin (%)"
    )

    @api.depends(
        'purchase_price',
        'purchase_price_vendor',
        'move_ids.product_id',
        'move_ids.product_id.qty_available',
        'move_ids.state',
        'qty_to_deliver'
    )
    def _compute_actual_margins(self):
        """ We want to use the margin based on average inventory valuation when the
        sale order line will be completely fulfilled (or has been fulfilled) from stock.
        For product not yet in stock we want to use the vendor price. We can also have
        blended calculations (partly on vendor price, partly on stock valuation). This
        occurs when an order has been or would be partially fulfilled from available
        stock.
        :return:
        """
        non_product_lines = self.filtered(lambda r: not r.product_id)
        non_product_lines.purchase_price_actual = 0.0
        non_product_lines.margin_actual = 0.0
        non_product_lines.margin_percent_actual = 0.0
        for line in self - non_product_lines:
            stock_missing = line._determine_missing_stock()
            if float_is_zero(stock_missing, precision_rounding=line.product_uom.rounding):
                # everything is coming from stock, use inventory valuation
                line.purchase_price_actual = line.purchase_price
            elif float_compare(line.product_uom_qty, stock_missing,
                               precision_rounding=line.product_uom.rounding) == 0:
                # everything is coming from the vendor, use vendor pricing
                line.purchase_price_actual = line.purchase_price_vendor
            else:
                # we have a mix, use blended pricing
                qty_from_stock = line.product_uom_qty - stock_missing
                line.purchase_price_actual = \
                    (stock_missing * line.purchase_price_vendor
                     + qty_from_stock * line.purchase_price) \
                    / line.product_uom_qty
            line.margin_actual = line.price_subtotal - (
                    line.purchase_price_actual * line.product_uom_qty)
            line.margin_percent_actual = line.price_subtotal and line.margin_actual / line.price_subtotal

    def _determine_missing_stock(self) -> float:
        """ Compute how much stock is missing to meet an order line's demand.  In the
        case of a quotation line, available stock is checked as if the order were to be
        placed immediately.

        :return: The quantity missing from available stock to fulfill the line, in
        the unit of measure matching self.product_uom.
        """
        self.ensure_one()
        is_order = self.order_id.state in ('sale', 'done')
        if is_order and self.qty_to_deliver == 0:
            return 0
        elif is_order and self.qty_to_deliver > 0:
            reserved = sum([q.reserved_quantity for q in self.move_ids.mapped('move_line_ids').mapped('quant_id')])
            missing = self.qty_to_deliver - reserved
            if float_compare(missing, 0.0,
                             precision_rounding=self.product_uom.rounding) == 1:
                # Not enough reserved, check stock
                missing = missing - self.product_id.qty_available
                if float_compare(missing, 0.0,
                                 precision_rounding=self.product_uom.rounding) == 1:
                    # Missing some stock to meet demand, return the quantity
                    return missing
                else:
                    # Enough stock available to meet this line's demand
                    return 0
            else:
                # Already have stock reserved
                return 0
        else:
            # This is a quotation, don't bother with stock reservations
            missing = self.product_uom_qty - self.product_id.qty_available
            if float_compare(missing, 0.0,
                             precision_rounding=self.product_uom.rounding) == 1:
                return missing
            else:
                return 0

    @api.depends('product_id', 'product_id.seller_ids',
                 'product_id.seller_ids.price')
    def _compute_purchase_price_vendor(self):
        for line in self:
            product = line.product_id
            suppinfos = product.seller_ids.sorted('sequence')
            if not suppinfos:
                line.purchase_price_vendor = 0.0
                continue
            suppinfo = suppinfos[0]
            purch_currency = suppinfo.currency_id
            to_cur = line.currency_id or line.order_id.currency_id
            line.purchase_price_vendor = purch_currency._convert(
                from_amount=suppinfo.price,
                to_currency=to_cur,
                company=line.company_id or self.env.company,
                date=line.order_id.date_order or fields.Date.today(),
                round=False,
            ) if to_cur and suppinfo.price else suppinfo.price

    @api.depends('purchase_price_vendor')
    def _compute_margin_vendor(self):
        for line in self:
            if not line.price_unit or float_is_zero(line.price_unit):
                line.margin_vendor = 0
                line.margin_percent_vendor = 0
                continue
            unit_margin = line.price_unit - line.purchase_price_vendor
            line.margin_percent_vendor = unit_margin / line.price_unit

            line.margin_vendor = unit_margin * line.product_uom_qty
