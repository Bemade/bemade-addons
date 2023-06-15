from odoo import api, fields, models, Command

class Partner(models.Model):
    _inherit = 'res.partner'

    equipment_count = fields.Integer(compute='_compute_equipment_count',
                                     string='Equipment Count')

    owned_equipment_ids = fields.One2many(comodel_name="bemade_fsm.equipment",
                                          inverse_name="partner_id",
                                          string="Owned Equipments")


    equipment_ids = fields.One2many(comodel_name='bemade_fsm.equipment',
                                    inverse_name='partner_location_id',
                                    string='Site Equipment')

    is_site_contact = fields.Boolean(string='Is a site contact',
                                     compute="_compute_is_site_contact")

    site_ids = fields.Many2many(string='Work Sites',
                                comodel_name='res.partner',
                                relation='res_partner_site_contact_rel',
                                column1='site_contact_id',
                                column2='site_id',
                                tracking=True)

    site_contacts = fields.Many2many(string='Site Contacts',
                                     comodel_name='res.partner',
                                     relation='res_partner_site_contact_rel',
                                     column1='site_id',
                                     column2='site_contact_id',
                                     domain=[('is_company', '=', False)],
                                     tracking=True)

    @api.depends('site_ids')
    def _compute_is_site_contact(self):
        for rec in self:
            rec.is_site_contact = rec.site_ids is not False

    @api.depends('equipment_ids')
    def _compute_equipment_count(self):
        for rec in self:
            all_equipmemt_ids = self.env['bemade_fsm.equipment'].search([('partner_id', '=', rec.id)])
            rec.equipment_count = len(all_equipmemt_ids)

    def get_root_ancestor(self):
        """ Returns the partner at the top of the parent-child hierarchy. """
        self.ensure_one()
        return self.parent_id and self.parent_id.get_root_ancestor() or self

    def get_first_company_ancestor(self):
        """ Returns the first ancestor that is a company """
        self.ensure_one()
        return self.is_company and self or self.parent_id and self.parent_id.get_first_company_ancestor()
