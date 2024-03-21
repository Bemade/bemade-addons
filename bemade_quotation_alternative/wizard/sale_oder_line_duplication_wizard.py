from odoo import models, fields

class SaleOrderLineDuplicationWizard(models.TransientModel):
    _name = 'sale.order.line.duplication.wizard'
    _description = 'Wizard for selecting sale order lines to duplicate'

    wizard_id = fields.Many2one('sale.order.duplication.wizard', required=True, ondelete='cascade', string="Wizard")
    sale_order_line_id = fields.Many2one('sale.order.line', string="Sale Order Line", required=True)
    to_duplicate = fields.Boolean(string="Duplicate?", default=True)
