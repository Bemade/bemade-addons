# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.addons.website.models import ir_http


class ResPartner(models.Model):
    _inherit = 'res.partner'

    surface = fields.Float(string='Surface (ha)')  # terrain
    lot_number = fields.Text(string='Lot Number')  # terrain

    ref_project = fields.Text(string='Project No')  # proprio
    intent_signing = fields.Boolean(string='Intent to sign')  # proprio
    cyberimpact = fields.Boolean(string='Cyberimpact')  # proprio
    specification_date = fields.Date(string='Specification date')  # proprio
    crm_stage_activity = fields.Text(string='Activity Stage')  # proprio

    property_count = fields.Integer(string='Property count', compute='_compute_property_count', store=True)
    is_owner = fields.Boolean(string='Is Owner', compute='_compute_property_count', store=True)

    sethy_firs_tdate = fields.Date(string='First membership date')  # member
    sethy_last_date = fields.Date(string='Last membership date')  # member
    sethy_renew_date = fields.Date(string='Next renew date date')  # member
    sethy_certification_date = fields.Date(string='Certification date date')  # member
    sethy_payment_type = fields.Text(string='Payment Type')  # member
    sethy_amount = fields.Float(string='Payment amount')  # Member

    is_property = fields.Boolean(
        string='Is Property',
        default=False
    )  # True if property, False if not

    interest_level = fields.Selection(
        selection=[
            ('1', 'None'),
            ('2', 'Low'),
            ('3', 'Average'),
            ('4', 'High')],
        string='Interest Level')  # proprio

    company_use = fields.Text(string='Company related')  # proprio

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

    # @api.depends('is_property')
    # def _forcing_company(self):
    #     for record in self:
    #         if record.is_property:
    #             record.is_company = True

    @api.onchange('is_property')
    def _onchange_is_property(self):
        """ Set is_company to True when is_property is set to True. """
        if self.is_property:
            self.is_company = True

    @api.onchange('is_company')
    def _onchange_is_company(self):
        """ Set is_property to False when is_company is set to False. """
        if not self.is_company:
            self.is_property = False

    @api.onchange('lot_number')
    def _onchange_lot_number(self):
        for lot in self:
            if lot.lot_number:
                lot.name = "Lot " + str(lot.lot_number)

    @api.depends('relation_property_ids')
    def _compute_property_count(self):
        for record in self:
            record.property_count = len(record.relation_property_ids)
            record.is_owner = record.property_count > 0