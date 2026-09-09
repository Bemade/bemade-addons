from odoo import models, fields, api

class StockWarehouseOrderpoint(models.Model):
    _name = 'stock.warehouse.orderpoint'
    _inherit = ['stock.warehouse.orderpoint', 'mail.thread', 'mail.activity.mixin']

    name = fields.Char(tracking=True)
    trigger = fields.Selection(tracking=True)
    active = fields.Boolean(tracking=True)
    snoozed_until = fields.Date(tracking=True)
    location_id = fields.Many2one(tracking=True)
    product_tmpl_id = fields.Many2one(tracking=True)
    product_id = fields.Many2one(tracking=True)
    product_min_qty = fields.Float(tracking=True)
    product_max_qty = fields.Float(tracking=True)
    qty_multiple = fields.Float(tracking=True)
    group_id = fields.Many2one(tracking=True)
    company_id = fields.Many2one(tracking=True)
    route_id = fields.Many2one(tracking=True)

    cost_supplier = fields.Float(
        string="Cost Supplier",
        compute="_compute_cost_supplier",
        store=False,
        help="The primary (first) vendor's price for this product, "
             "taken from the Purchase tab (product.supplierinfo).",
    )
    cost_subtotal = fields.Float(
        string="Cost Sub-Total",
        compute="_compute_cost_subtotal",
        store=False,
        aggregator="sum",
        help="To-Order quantity multiplied by the primary vendor's price.",
    )

    @api.depends(
        "product_tmpl_id.seller_ids",
        "product_tmpl_id.seller_ids.sequence",
        "product_tmpl_id.seller_ids.price",
    )
    def _compute_cost_supplier(self):
        for orderpoint in self:
            sellers = orderpoint.product_tmpl_id.seller_ids
            orderpoint.cost_supplier = sellers[0].price if sellers else 0.0

    @api.depends("qty_to_order", "cost_supplier")
    def _compute_cost_subtotal(self):
        for orderpoint in self:
            orderpoint.cost_subtotal = (
                (orderpoint.qty_to_order or 0.0) * orderpoint.cost_supplier
            )
