from odoo import api, fields, models, Command


class Partner(models.Model):
    _inherit = 'res.partner'

    equipment_count = fields.Integer(compute='_compute_equipment_count', string='Equipment Count')

    owned_equipment_ids = fields.One2many(
        comodel_name="bemade_fsm.equipment",
        compute="_compute_owned_equipment_ids",
        string="Owned Equipments"
    )

    equipment_ids = fields.One2many(
        comodel_name='bemade_fsm.equipment',
        inverse_name='partner_location_id',
        string='Site Equipment'
    )

    is_site_contact = fields.Boolean(
        string='Is a site contact',
        compute="_compute_is_site_contact",
        search="_search_is_site_contact",
    )

    site_ids = fields.Many2many(
        string='Work Sites',
        comodel_name='res.partner',
        relation='res_partner_site_contact_rel',
        column1='site_contact_id',
        column2='site_id',
        tracking=True
    )

    site_contacts = fields.Many2many(
        string='Site Contacts',
        comodel_name='res.partner',
        relation='res_partner_site_contact_rel',
        column1='site_id',
        column2='site_contact_id',
        domain=[('is_company', '=', False)],
        tracking=True
    )

    work_order_contacts = fields.Many2many(
        string='Work Order Recipients',
        comodel_name='res.partner',
        relation='res_partner_work_order_contacts_rel',
        column1='res_partner_id',
        column2='work_order_contact_id',
        domain=[('is_company', '=', False)],
        tracking=True
    )

    @api.depends(
        'equipment_ids',
        'child_ids.company_type',
        'child_ids.equipment_ids'
    )
    def _compute_owned_equipment_ids(self):
        for rec in self:
            ids = rec.equipment_ids | rec.child_ids.filtered(
                lambda l: l.company_type == 'company').mapped('equipment_ids')
            rec.owned_equipment_ids = ids or False

    @api.depends('site_ids')
    def _compute_is_site_contact(self):
        for rec in self:
            rec.is_site_contact = rec.site_ids is not False

    @api.depends('equipment_ids')
    def _compute_equipment_count(self):
        for rec in self:
            all_equipment_ids = self.env['bemade_fsm.equipment'].search(
                [('partner_location_id', '=', rec.id)])
            rec.equipment_count = len(all_equipment_ids)

    @api.model
    def _search_is_site_contact(self, operator, value):
        return [('site_contacts', '!=', False)]
