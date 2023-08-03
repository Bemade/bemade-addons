# -*- coding: utf-8 -*-
# from odoo import http


# class .repos/bemade-addons/bemadeQuotationAlternative(http.Controller):
#     @http.route('/.repos/bemade-addons/bemade_quotation_alternative/.repos/bemade-addons/bemade_quotation_alternative', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/.repos/bemade-addons/bemade_quotation_alternative/.repos/bemade-addons/bemade_quotation_alternative/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('.repos/bemade-addons/bemade_quotation_alternative.listing', {
#             'root': '/.repos/bemade-addons/bemade_quotation_alternative/.repos/bemade-addons/bemade_quotation_alternative',
#             'objects': http.request.env['.repos/bemade-addons/bemade_quotation_alternative..repos/bemade-addons/bemade_quotation_alternative'].search([]),
#         })

#     @http.route('/.repos/bemade-addons/bemade_quotation_alternative/.repos/bemade-addons/bemade_quotation_alternative/objects/<model(".repos/bemade-addons/bemade_quotation_alternative..repos/bemade-addons/bemade_quotation_alternative"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('.repos/bemade-addons/bemade_quotation_alternative.object', {
#             'object': obj
#         })
