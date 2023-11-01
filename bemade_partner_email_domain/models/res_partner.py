from odoo import api, fields, models, Command

class Partner(models.Model):
    _inherit = 'res.partner'

    email_domain = fields.Char(string='Email Domain')

    @api.onchange('email')
    def _check_parent_from_email_domain(self):
        for rec in self:
            if rec.parent_id:
                continue
            try:
                # Split the email address on '@' and get the domain part
                if rec.email:
                    email_domain = rec.email.split('@')[1].strip()
                else:
                    continue
            except IndexError:
                # If there's no '@' symbol, the email address is invalid
                return False

            # Loop while there's more than one part in the domain (e.g., subdomain.domain.tld)
            while '.' in email_domain:
                # If the current email domain matches the main domain, return True
                company_domain = self.env['res.partner'].search([('email_domain', 'ilike', email_domain)])
                if company_domain:
                    rec.parent_id = company_domain.id
                    return

                # If not, drop the part before the first '.' to check the next level
                email_domain = email_domain.split('.', 1)[1]

    @api.model_create_multi
    def create(self, vals_list):
        res = super(Partner, self).create(vals_list)
        res._check_parent_from_email_domain()
        return res

    def write(self, vals):
        res = super(Partner, self).write(vals)
        if 'email' in vals:
            self._check_parent_from_email_domain()
        return res
