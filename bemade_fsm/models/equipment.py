from odoo import api, fields, models


class Equipment(models.Model):
    _name = 'bemade_fsm.equipment'
    _rec_name = 'complete_name'
    _description = 'Field service equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    pid_tag = fields.Char(string="P&ID Tag", tracking=True)

    name = fields.Char(string="Name", tracking=True, required=True)

    complete_name = fields.Char(string="Equipment Name", compute="_compute_complete_name", store=True)

    tag_ids = fields.Many2many(
        comodel_name='bemade_fsm.equipment.tag',
        string='Application',
        help="Classify and analyze your equipment categories like: Boiler, Laboratory, Waste water, Pure water"
    )

    description = fields.Text(string="Description", tracking=True)

    partner_location_id = fields.Many2one(
        comodel_name='res.partner',
        string="Physical Address",
        tracking=True,
        ondelete='cascade'
    )

    location_notes = fields.Text(string="Physical Location Notes", tracking=True)

    task_ids = fields.Many2many(
        comodel_name='project.task',
        relation="bemade_fsm_task_equipment_rel",
        column1="equipment_id",
        column2="task_id",
        string='Interventions'
    )

    @api.depends('partner_location_id')
    def _compute_partner(self):
        for rec in self:
            rec.partner_id = rec.partner_location_id and rec.partner_location_id.root_ancestor

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            equipments = self.search([
                '|', '|', '|',
                ('pid_tag', operator, name),
                ('name', operator, name),
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

    @api.depends('pid_tag', 'name')
    def _compute_complete_name(self):
        for rec in self:
            tag_part = "[%s] " % rec.pid_tag if rec.pid_tag else ""
            name = rec.name or ""
            rec.complete_name = tag_part + name
