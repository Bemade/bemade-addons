# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class .repos/bemade-addons/bemade_quotation_alternative(models.Model):
#     _name = '.repos/bemade-addons/bemade_quotation_alternative..repos/bemade-addons/bemade_quotation_alternative'
#     _description = '.repos/bemade-addons/bemade_quotation_alternative..repos/bemade-addons/bemade_quotation_alternative'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
