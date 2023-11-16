from odoo import fields, models, api


class ModelName(models.Model):
    _inherit = 'sale.order'

    def action_create_alternative(self):
        return {
            'name': 'Create Alternative',
            'type': 'ir.actions.act_window',
            'res_model': 'bemade.quotation.alternative',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
            }
        }