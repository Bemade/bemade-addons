from odoo import models, fields, api, _


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    account_type_ids = fields.One2many('delivery.account.type', 'carrier_id',
                                       string='Account Types')
