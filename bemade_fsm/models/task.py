from odoo import fields, models, api, Command, _
from odoo.exceptions import ValidationError, UserError
from odoo.osv import expression
from collections import defaultdict, namedtuple


class Task(models.Model):
    _inherit = "project.task"

    equipment_ids = fields.Many2many(comodel_name="bemade_fsm.equipment",
                                     relation="bemade_fsm_task_equipment_rel",
                                     column1="task_id",
                                     column2="equipment_id",
                                     string="Equipment to Service",
                                     tracking=True, )

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

    planned_date_begin = fields.Datetime("Start Date", tracking=True,
                                         task_dependency_tracking=True,
                                         compute="_compute_planned_dates",
                                         inverse="_inverse_planned_dates",
                                         store=True)
    planned_date_end = fields.Datetime("End Date", tracking=True,
                                       task_dependency_tracking=True,
                                       compute="_compute_planned_dates",
                                       inverse="_inverse_planned_dates",
                                       store=True)

    # Override related field to make it return false if this is an FSM subtask
    allow_billable = fields.Boolean(string="Can be billed",
                                    related=False,
                                    compute="_compute_allow_billable",
                                    store=True)

    visit_id = fields.Many2one(comodel_name='bemade_fsm.visit')

    is_complete = fields.Boolean(compute="_compute_is_complete")

    # user_id = fields.Many2one('res.users', compute='_compute_user_id')
    #
    # @api.depends('user_ids')
    # def _compute_user_id(self):
    #     for rec in self:
    #         rec.user_id = rec.user_ids and rec.user_ids[0] or 0

    def _get_closed_stage_by_project(self):
        """ Gets the stage representing completed tasks for each project in
        self.project_id. Copied from industry_fsm/.../project.py:217-221
        for consistency.

        :returns: Dict of project.project -> project.task.type"""
        return {
            project:
                project.type_ids.filtered(lambda stage: stage.is_closed)[:1]
                or project.type_ids[-1:]
            for project in self.project_id
        }

    @api.depends('project_id', 'stage_id.is_closed')
    def _compute_is_complete(self):
        closing_stages = self._get_closed_stage_by_project()
        for rec in self:
            rec.is_complete = rec.stage_id == (rec.project_id
                                               and closing_stages[rec.project_id])

    def _get_related_planning_slots(self):
        domain = expression.AND([
            self._get_domain_compute_forecast_hours(),
            [('task_id', 'in', self.ids + self._get_all_subtasks().ids)]
        ])
        return self.env['planning.slot'].search(domain)

    @api.depends('forecast_hours')
    def _compute_planned_dates(self):
        forecast_data = self._get_related_planning_slots()
        mapped_data = {}
        TimeSpan = namedtuple('timespan', ['start', 'end'])
        for d in forecast_data:
            if d not in mapped_data:
                mapped_data.update({d: TimeSpan(d.start_datetime, d.end_datetime)})
                continue
            if mapped_data[d].start > d.start_datetime:
                mapped_data[d].start = d.start_datetime
            if mapped_data[d].end < d.end_datetime:
                mapped_data[d].end = d.end_datetime
        for rec in self:
            if rec not in mapped_data:
                if not rec.planned_date_end:
                    rec.planned_date_end = False
                if not rec.planned_date_begin:
                    rec.planned_date_begin = False
                continue
            rec.planned_date_begin, rec.planned_date_end = mapped_data[rec]

    def _inverse_planned_dates(self):
        """ Modifying the planned dates for tasks with existing planning records
        (planning.slot) has no defined safe behaviour, so we block it."""
        if self._get_related_planning_slots():
            raise UserError(_("Modifying the planned start or end time on a task is not "
                              "permitted when that task already has planning records "
                              "associated to it. Please modify or delete the planning "
                              "records instead."))

    @api.depends('sale_line_id.order_id.site_contacts',
                 'sale_line_id.order_id.work_order_contacts')
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

    @api.depends('parent_id.visit_id', 'project_id.is_fsm', 'project_id.allow_billable')
    def _compute_allow_billable(self):
        for rec in self:
            # If an FSM task has a parent that is linked to an SO line, then the parent is the billable one
            if rec.parent_id and not rec.parent_id.visit_id and rec.project_id and rec.project_id.is_fsm:
                rec.allow_billable = False
            else:
                rec.allow_billable = rec.project_id.allow_billable
