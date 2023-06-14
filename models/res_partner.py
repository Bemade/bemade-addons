from odoo import api, fields, models


class Partner(models.Model):
    _inherit = 'res.partner'

    equipment_count = fields.Integer(compute='_compute_equipment_count',
                                     string='Equipment Count')

    equipment_ids = fields.One2many(comodel_name='bemade_fsm.equipment',
                                    inverse_name='partner_id',
                                    string='Equipments')

    equipment_location_count = fields.Integer(compute='_compute_equipment_location_count',
                                              string='Equipment Location Count')

    equipment_location_ids = fields.One2many(comodel_name='bemade_fsm.equipment.location',
                                             inverse_name='partner_id',
                                             string='Equipment Location')

    is_site = fields.Boolean(string='Is an Equipment Site',
                             tracking=True,
                             default=False,
                             help="Check if the contact is an equipment site, otherwise it is not in that list")

    is_site_contact = fields.Boolean(string='Is a site contact',
                                     tracking=True,
                                     default=False,
                                     help="Check if the contact is a site contact, otherwise it is a not in that list")

    @api.depends('equipment_ids')
    def _compute_equipment_count(self):
        for rec in self:
            all_equipmemt_ids = self.env['bemade_fsm.equipment'].search([('partner_id', '=', rec.id)])
            rec.equipment_count = len(all_equipmemt_ids)

    @api.depends('equipment_location_ids')
    def _compute_equipment_location_count(self):
        for rec in self:
            all_equipmemt_location_ids = self.env['bemade_fsm.equipment.location'].search([('partner_id', '=', rec.id)])
            rec.equipment_location_count = len(all_equipmemt_location_ids)
