from odoo import models, fields, api, _, Command


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    billing_contacts = fields.Many2many(
        comodel_name='res.partner',
        string='Billing Contacts',
        compute='_compute_billing_contacts',
        inverse='_inverse_billing_contacts',
        store=True
    )

    @api.depends('partner_id')
    def _compute_billing_contacts(self):
        for rec in self:
            rec.billing_contacts = rec.partner_id.billing_contacts

    def _inverse_billing_contacts(self):
        pass
