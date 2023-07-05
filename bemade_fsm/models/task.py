from odoo import fields, models, api, Command, _
from odoo.exceptions import ValidationError


class Task(models.Model):
    _inherit = "project.task"

    equipment_id = fields.Many2one("bemade_fsm.equipment", string="Equipment to Service", tracking=True)

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

    # Override related field to make it return false if this is an FSM subtask
    allow_billable = fields.Boolean(string="Can be billed",
                                    related=False,
                                    compute="_compute_allow_billable",)
    @api.depends('sale_line_id.order_id.site_contacts', 'sale_line_id.order_id.work_order_contacts')
    def _compute_contacts(self):
        """ The work order contacts and site contacts for a given task are taken from the sale order if the task
        is related to one, and from the task's customer if there is no sale order related to the task."""
        for rec in self:
            site_contacts = self.sale_line_id and self.sale_line_id.order_id.site_contacts or \
                            self.partner_id.site_contacts
            work_order_contacts = self.sale_line_id and self.sale_line_id.order_id.work_order_contacts or \
                                  self.partner_id.work_order_contacts
            rec.write({
                'site_contacts': [Command.set(site_contacts.ids)],
                'work_order_contacts': [Command.set(work_order_contacts.ids)]
            })

    def _inverse_contacts(self):
        """ If the task is linked to a sales order, the sales order should have its contacts updated to match."""
        for rec in self:
            if rec.sale_line_id:
                rec.sale_line_id.order_id.write({
                    'work_order_contacts': [Command.set(rec.work_order_contacts.ids)],
                    'site_contacts': [Command.set(rec.site_contacts.ids)],
                })

    @api.depends('parent_id', 'project_id')
    def _compute_allow_billable(self):
        for rec in self:
            if rec.parent_id and rec.project_id and rec.project_id.is_fsm:
                rec.allow_billable = False
            else:
                rec.allow_billable = rec.project_id.allow_billable
