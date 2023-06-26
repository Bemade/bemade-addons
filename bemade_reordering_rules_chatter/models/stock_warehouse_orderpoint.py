from odoo import models, fields

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
