from odoo import http
from odoo.http import request

class ValidateEmailController(http.Controller):

    @http.route(['/validate_email/<model("res.partner"):partner>/<token>'], type='http', auth="public", website=True)
    def validate_email(self, partner, token, **kw):
        if partner.email_validation_token != token:
            return request.render("bemade_validate_partner_email.invalid_token", {})
        else:
            partner.sudo().write({'email_validated': True})
            return request.render("bemade_validate_partner_email.email_validated", {})
