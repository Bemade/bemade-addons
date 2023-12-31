# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.addons.website.models import ir_http


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _property_category_id(self):
        return self.env.ref('bemade_sethy_configuration.partner_tag_property', raise_if_not_found=False)

    surface = fields.Float(string='Surface (ha)')  # terrain
    lot_number = fields.Text(string='Lot Number')  # terrain

    ref_project = fields.Text(string='Project No')  # proprio
    intent_signing = fields.Boolean(string='Intent to sign')  # proprio
    cyberimpact = fields.Boolean(string='Cyberimpact')  # proprio
    specification_date = fields.Date(string='Specification date')  # proprio
    crm_stage_activity = fields.Text(string='Activity Stage')  # proprio

    property_count = fields.Integer(string='Property count', compute='_compute_property_count', store=True)
    is_owner = fields.Boolean(string='Is Owner', compute='_compute_property_count', store=True)

    sethy_first_date = fields.Date(string='First membership date')  # member
    sethy_last_date = fields.Date(string='Last membership date')  # member
    sethy_renew_date = fields.Date(string='Next renew date date')  # member
    sethy_certification_date = fields.Date(string='Certification date date')  # member
    sethy_payment_type = fields.Text(string='Payment Type')  # member
    sethy_amount = fields.Float(string='Payment amount')  # Member

    is_property = fields.Boolean(
        string='Is Property',
        default=False,
        compute='_compute_is_property',
        inverse='_inverse_is_property',
        store=True
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

    @api.depends('category_id')
    def _compute_is_property(self):
        property_tag = self.env.ref('bemade_sethy_configuration.partner_tag_property', raise_if_not_found=False)
        for partner in self:
            # Check if the property tag exists.  If it doesn't, set is_property to False.
            # Because module installation order is not guaranteed, the tag may not exist yet when this method is called.
            # This is due to store=True on the is_property field.
            if property_tag is None:
                partner.is_property = False
            else:
                partner.is_property = property_tag and property_tag in partner.category_id

    def _inverse_is_property(self):
        property_tag = self.env.ref('bemade_sethy_configuration.partner_tag_property', raise_if_not_found=False)
        for partner in self:
            if partner.is_property and property_tag not in partner.category_id and property_tag:
                partner.category_id |= property_tag
            elif not partner.is_property and property_tag in partner.category_id:
                partner.category_id -= property_tag

    @api.depends('relation_property_ids')
    def _compute_property_count(self):
        for record in self:
            record.property_count = len(record.relation_property_ids)
            record.is_owner = record.property_count > 0

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
    @api.onchange('lot_number')
    def _onchange_lot_number(self):
        for lot in self:
            if lot.lot_number:
                lot.name = "Lot " + str(lot.lot_number)

    @api.model_create_multi
    def create(self, vals_list):
        # Create Partner records using the super function
        records = super().create(vals_list)
        user_company = self.env.user.company_id

        # Update the records where 'state_id' or 'country_id' isn't provided
        for record in records:
            if not record.state_id or not record.country_id:
                if not record.state_id and user_company.state_id:
                    record.write({
                        'state_id': user_company.state_id.id,
                    })
                if not record.country_id and user_company.country_id:
                    record.write({
                        'country_id': user_company.country_id.id
                    })
            if record.name.startswith("Lot "):
                record.lot_number = record.name[4:]
            record._inverse_is_property()
        return records

    @api.onchange('name')
    def _onchange_name(self):
        for record in self:
            if record.name and record.name.startswith("Lot "):
                record.lot_number = record.name[4:]

    def write(self, vals):
        result = super(ResPartner, self).write(vals)
        self._inverse_is_property()
        return result

    @api.onchange('category_id')
    def _onchange_category_id(self):
        self._compute_is_property()