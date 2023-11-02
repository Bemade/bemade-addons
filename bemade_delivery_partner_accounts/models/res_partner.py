from odoo import models, fields, api, _


class Partner(models.Model):
    _inherit = 'res.partner'

    delivery_account_ids = fields.Many2many('delivery.account', string='Delivery Accounts',
                                            relation='delivery_account_partner_rel',
                                            column1='partner_id', column2='account_id')
    default_delivery_account_id = fields.Many2one('delivery.account', string='Default Delivery Account')

    def write(self, values):
        super().write(values)
        if 'delivery_account_ids' in values:
            for rec in self.filtered(lambda r: not r.default_delivery_account_id and rec.delivery_account_ids):
                rec.default_delivery_account_id = rec.delivery_account_ids[0]
        if 'default_delivery_account_id' in values:
            for rec in self.filtered(lambda r: not r.delivery_account_ids and r.default_delivery_account_id):
                rec.delivery_account_ids = [(4, rec.default_delivery_account_id.id)]

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res.filtered(lambda r: not r.default_delivery_account_id and rec.delivery_account_ids):
            rec.default_delivery_account_id = rec.delivery_account_ids[0]
        for rec in res.filtered(lambda r: not r.delivery_account_ids and r.default_delivery_account_id):
            rec.delivery_account_ids = [(4, rec.default_delivery_account_id.id)]
        return res
