from odoo import api, fields, models, Command
import uuid

from odoo.addons.website.controllers.main import Website


class Partner(models.Model):
    _inherit = 'res.partner'

    email_domain = fields.Char(string='Email Domain')
    is_subdivision = fields.Boolean(string='Subdivision', default=False)
    access_token = fields.Char(string='Access Token')

    def _generate_access_token(self):
        return uuid.uuid4().hex

    def _send_selection_email(self, division_companies):
        self.ensure_one()
        # Generate a token and save it to the partner
        access_token = self._generate_access_token()
        print(f'partner id: {self.id}')
        self.write({'access_token': access_token})

        # Now include the token in the links
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        links = {
            company.name: (f'{base_url}/select_division_company?partner_id={self.id}&access_token={access_token}&division_id={company.id}') for company in division_companies
        }

        print(f'links: {links}')
        # Render the email template and send the email
        template = self.env.ref('bemade_partner_email_domain.email_template_select_parent')
        template.with_context(links=links).send_mail(self.id, force_send=True)

    # @api.onchange('email')
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
                    if len(company_domain) > 1:
                        rec._send_selection_email(company_domain)
                    else:
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
