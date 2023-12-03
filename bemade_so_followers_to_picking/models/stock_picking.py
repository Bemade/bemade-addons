from odoo import models, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'


@api.model_create_multi
def create(self, vals_list):
    pickings = super().create(vals_list)

    for picking, vals in zip(pickings, vals_list):
        if 'origin' in vals:
            sale_order = self.env['sale.order'].search([('name', '=', vals['origin'])], limit=1)
            if sale_order:
                for follower in sale_order.message_follower_ids:
                    picking.message_subscribe(partner_ids=[follower.partner_id.id])

    return pickings
