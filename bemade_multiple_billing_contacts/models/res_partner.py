from odoo import models, fields, api, _, Command


class Partner(models.Model):
    _inherit = 'res.partner'

    billing_contacts = fields.Many2many(
        string='Default Billing Contacts',
        comodel_name='res.partner',
        compute='_compute_billing_contacts',
        inverse='_inverse_billing_contacts'
    )

    potential_billing_contacts = fields.Many2many(
        comodel_name='res.partner',
        compute='_compute_billing_contacts'
    )

    @api.depends('child_ids.type')
    def _compute_billing_contacts(self):
        for rec in self:
            rec.billing_contacts = rec.child_ids.filtered(lambda r: r.type == 'invoice')
            rec.potential_billing_contacts = rec.child_ids | rec.parent_id.child_ids if rec.is_company else None

    @api.depends('billing_contacts')
    def _inverse_billing_contacts(self):
        for partner in self.mapped('billing_contacts'):
            partner.type = 'invoice'
