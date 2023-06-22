from odoo import fields, models, api


class Task(models.Model):
    _inherit = "project.task"

    equipment_id = fields.Many2one("bemade_fsm.equipment", string="Target Equipment")
