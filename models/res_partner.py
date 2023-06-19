from odoo import models, fields, api, _, Command


class Partner(models.Model):
    _inherit = 'res.partner'

    def _billing_contacts_domain(self):
        self.ensure_one()
        return [('is_company', '=', False), ('root_ancestor', '=', self.root_ancestor)]
    billing_contacts = fields.Many2many(string='Default Billing Contacts',
                                        comodel_name='res.partner',
                                        relation='res_partner_billing_contact_rel',
                                        column1='billing_contact_id',
                                        column2='billed_partner_id',
                                        domain=_billing_contacts_domain,
                                        tracking=True)