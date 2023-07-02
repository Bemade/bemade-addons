from odoo import models, fields, api, _

class Partner(models.Model):
    _inherit = 'res.partner'

    email_validated = fields.Boolean(string='Email Validated', default=False)

    email_validation_token = fields.Char(string="Email Validation Token", copy=False)

    @api.model
    def create(self, vals):
        if'Email' in vals:
            vals['email_validated'] = False
        partner = super().create(vals)
        partner._send_validation_email()
        return partner

    def write(self, vals):
        if 'email' in vals:
            vals['email_validated'] = False
        res = super().write(vals)
        for partner in self:
            partner._send_validation_email()
        return res

    def send_validation_email(self):
        for partner in self:
            token = misc.generate_tracking_token()
            partner.email_validation_token = token
            partner.validation_email_template_id.send_mail(partner.id)
