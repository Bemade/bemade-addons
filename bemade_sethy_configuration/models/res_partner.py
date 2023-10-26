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
    crm_stage_activity = fields.Text(string='Activity Stage')

    interest_level = fields.Selection(
        selection=[
            ('1', 'None'),
            ('2', 'Low'),
            ('3', 'Average'),
            ('4', 'High')],
        string='Interest Level')

    company_use = fields.Text(string='Company related')

    relation_owner_ids = fields.One2many(
        "res.partner.relation.all",
        compute="_compute_owner_ids",
        string="Owner ids"
    )

    relation_property_ids = fields.One2many(
        "res.partner.relation.all",
        compute="_compute_property_ids",
        string="Property ids"
    )

    @api.depends('relation_all_ids')
    def _compute_owner_ids(self):
        for record in self:
            record.relation_owner_ids = record.relation_all_ids.filtered(
                lambda line: (
                        line.type_id.name == 'Owner' and not line.is_inverse)
            )

    @api.depends('relation_all_ids')
    def _compute_property_ids(self):
        for record in self:
            record.relation_property_ids = record.relation_all_ids.filtered(
                lambda line: (
                        line.type_id.name == 'Owner' and line.is_inverse)
            )
