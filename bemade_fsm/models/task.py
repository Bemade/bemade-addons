from odoo import fields, models, api


class Task(models.Model):
    _inherit = "project.task"

    work_order_contacts = fields.Many2many(comodel_name="res.partner",
                                           relation="task_work_order_contact_rel",
                                           column1="task_id",
                                           column2="res_partner_id",
                                           compute="_compute_contacts",
                                           inverse="_inverse_contacts",
                                           store=True)
    site_contacts = fields.Many2many(comodel_name="res.partner",
                                           relation="task_site_contact_rel",
                                           column1="task_id",
                                           column2="res_partner_id",
                                           compute="_compute_contacts",
                                           inverse="_inverse_contacts",
                                           store=True)
    equipment_ids = fields.Many2many(comodel_name="bemade_fsm.equipment",
                                     relation="task_equipment_rel",
                                     column1="task_id",
                                     column2="res_partner_id",
                                     compute="_compute_equipment",
                                     inverse="_inverse_equipment",
                                     store=True)
