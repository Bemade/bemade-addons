from odoo import api, fields, models


class EquipmentTag(models.Model):

    _name = "bemade_fsm.equipment.tag"
    _description = 'Field service equipment category'

    name = fields.Char('Name', required=True, translate=True)
    color = fields.Integer('Color Index', default=10)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists !"),
    ]


class EquipmentType(models.Model):
    _name = 'bemade_fsm.equipment.type'
    _description = 'Field service equipment type'
    _order = 'id'

    name = fields.Char(string='Intervention Name', required=True, translate=True)


class EquipmentLocation(models.Model):
    _name = 'bemade_fsm.equipment.location'
    _description = 'Field service location for equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True, translate=True)

    more_info = fields.Char(string='MOre info')

    partner_id = fields.Many2one(comodel_name='res.partner',
                                 string="Address",
                                 tracking=True,
                                 domain="[('is_site', '=', True)]",
                                 required=True)

    equipment_count = fields.Integer(compute='_compute_equipment_count',
                                     string='Equipment Count')

    equipment_ids = fields.One2many(comodel_name='bemade_fsm.equipment',
                                    inverse_name='equipment_location_id',
                                    string='Equipments')

    @api.depends('equipment_ids')
    def _compute_equipment_count(self):
        for rec in self:
            all_equipmemt_ids = self.env['bemade_fsm.equipment'].search([('equipment_location_id', '=', rec.id)])
            rec.equipment_count = len(all_equipmemt_ids)


class Equipment(models.Model):
    _name = 'bemade_fsm.equipment'
    _rec_name = 'complete_name'
    _description = 'Field service equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    pid_tag = fields.Char(string="P&ID Tag", tracking=True)

    name = fields.Char(string="Name", tracking=True, required=True)

    complete_name = fields.Char(string="Equipment Name", compute="_compute_complete_name", store=True)

    tag_ids = fields.Many2many('bemade_fsm.equipment.tag',
                               string='Application',
                               tracking=True,
                               help="Classify and analyze your equipment categories like: Boiler, Laboratory, "
                                    "Waste water, Pure water")

    partner_id = fields.Many2one('res.partner',
                                 string="Owner",
                                 tracking=True,
                                 domain="[('is_company', '=', True)]",
                                 required=True)

    description = fields.Text(string="Description",
                              tracking=True,
                              )

    partner_location_id = fields.Many2one('res.partner',
                                          string="Physical Location",
                                          tracking=True,
                                          domain="[('parent_id', '=', partner_id), ('is_site', '=', 'True')]",
                                          required=True)

    equipment_location_id = fields.Many2one('bemade_fsm.equipment.location',
                                            string="Location",
                                            tracking=True,
                                            domain="[('partner_id', '=', partner_location_id)]")

    location_notes = fields.Text(string="Physical Location Notes",
                                 tracking=True,
                                 )

    intervention_ids = fields.One2many(comodel_name='project.task',
                                       inverse_name='equipment_id',
                                       string='Interventions')

    @api.depends('pid_tag', 'name')
    def _compute_complete_name(self):
        for rec in self:
            rec.complete_name = "[%s] %s" % (rec.pid_tag or ' ', rec.name)

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            equipments = self.search([
                    '|', '|', '|',
                    ('pid_tag', operator, name),
                    ('name', operator, name),
                    ('partner_id.name', operator, name),
                    ('partner_location_id.name', operator, name)],
                limit=limit)
        else:
            equipments = self.search(args, limit=limit)
        return equipments.name_get()
