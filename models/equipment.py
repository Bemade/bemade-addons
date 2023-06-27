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
                                 compute="_compute_partner",
                                 search="_search_partner",)

    description = fields.Text(string="Description",
                              tracking=True)

    partner_location_id = fields.Many2one('res.partner',
                                          string="Physical Address",
                                          tracking=True,
                                          ondelete='cascade')

    location_notes = fields.Text(string="Physical Location Notes",
                                 tracking=True)
    task_ids = fields.One2many(comodel_name='project.task',
                               inverse_name='equipment_id',
                               string='Interventions')

    @api.depends('partner_location_id')
    def _compute_partner(self):
        for rec in self:
            rec.partner_id = rec.partner_location_id and rec.partner_location_id.root_ancestor

    @api.model
    def _search_partner(self, operator, value):
        return [('partner_location_id.root_ancestor', operator, value)]

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

    def action_view_equipment(self):
        return {
            'name': 'Equipment',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'context': self.env.context,
            'res_model': 'bemade_fsm.equipment',
            'type': 'ir.actions.act_window',
        }
