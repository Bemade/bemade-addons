# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.addons.website.models import ir_http


class ResPartner(models.Model):
    _inherit = 'res.partner'

    surface = fields.Float(string='Surface (ha)')
    lot_number = fields.Text(string='Lot Number')
    ref_project = fields.Text(string='Project No')
    intent_signing = fields.Boolean(string='Intent to sign')
    cyberimpact = fields.Boolean(string='Cyberimpact')
    specification_date = fields.Date(string='Specification date')
    crm_stage_activity = fields.Text(string='Project No')
    interest_level = fields.Selection(selection=[('1','None'),
                                                 ('2','Low'),
                                                 ('3','Average'),
                                                 ('4','High')], string='Interest Level')
    company_use = fields.Text(string='Company')


