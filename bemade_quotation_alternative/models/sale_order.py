from odoo import fields, models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_duplicate_order(self):
        self.ensure_one()
        action = self.env.ref('bemade_quotation_alternative.sale_order_duplication_wizard_action').read()[0]
        action['context'] = {
            'default_original_order_id': self.id,
        }
        return action
