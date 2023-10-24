# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.addons.website.models import ir_http


class ResPartner(models.Model):
    _inherit = 'res.partner'

    surface = fields.Float(string='Surface')
    ref_project = fields.Text(string='Project')
    intent = fields.Boolean(string='Intent')
    
