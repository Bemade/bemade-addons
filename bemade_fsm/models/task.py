from odoo import fields, models, api


class Task(models.Model):
    _inherit = "project.task"

    equipment_id = fields.Many2one("bemade_fsm.equipment", string="Target Equipment")

    work_order_contacts = fields.Many2many(related='sale_line_id.order_id.work_order_contacts')
    site_contacts = fields.Many2many(related='sale_line_id.order_id.site_contacts')
    equipment_ids = fields.Many2many(related='sale_line_id.order_id.equipment_ids')
