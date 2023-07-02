from odoo import http
from odoo.http import request

class EmailValidationController(http.Controller):

    @http.route('/email_validation/<int:partner_id>/<token>', type='http', auth='public', website=True)
    def email_validation(self, partner_id, token):
        partner = request.env['res.partner'].sudo().browse(partner_id)
        if partner and partner.validation_token == token:
            partner.sudo().write({'email_validated': True})
            return "Email validated!"
        else:
            return "Invalid validation link."
