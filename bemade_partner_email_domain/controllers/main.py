from odoo import http
from odoo.http import request

class DivisionCompanyController(http.Controller):

    @http.route('/select_division_company', type='http', auth='public', methods=['GET'])
    def select_division_company(self, partner_id, access_token, division_id, **kwargs):
        partner = request.env['res.partner'].sudo().search([
            ('id', '=', int(partner_id)),
            ('access_token', '=', access_token)
        ])

        if not partner:
            return request.render('website.404')