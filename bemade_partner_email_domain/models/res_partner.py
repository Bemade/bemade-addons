from odoo import api, fields, models, Command

from odoo.addons.website.controllers.main import Website


class Partner(models.Model):
    _inherit = 'res.partner'

    domain_identifier = fields.Boolean(string='Domain identifier', default=False)
    email_domain = fields.Char(string='Email Domain')
    is_subdivision = fields.Boolean(string='Subdivision', default=False)
    access_token = fields.Char(string='Access Token')

    def _generate_access_token(self):
        return uuid.uuid4().hex

    def _send_selection_email(self, partner, division_companies):
        # Generate a token and save it to the partner
        access_token = self._generate_access_token()
        partner.write({'access_token': access_token})

        # Now include the token in the links
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        links = {
            company.id: f'{base_url}/select_division_company?partner_id={partner.id}&access_token={access_token}&division_id={company.id}'
            for company in division_companies
        }

        # Render the email template and send the email
        template = self.env.ref('bemade_partner_email_domain.mail_template_selection_email')
        template.with_context(links=links).send_mail(partner.id, force_send=True)

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
                    if company_domain.domain_identifier:
                        division_company = self.env['res.partner'].search([('parent_id', '=', company_domain.id),
                                                                           ('is_company', '=', True)])
                        # need to send an email to the new partner asking him to select his parent in the liste
                        # of company under domain identifier
                        if division_company:
                            # Send an email to the partner with the division company selection link
                            if len(division_company) > 1:
                                self._send_selection_email(self, division_company)
                            else:
                                rec.parent_id = division_company[0].id
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
