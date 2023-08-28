from odoo import fields, models, api, Command, _
from odoo.exceptions import ValidationError, UserError
from odoo.osv import expression
from collections import defaultdict, namedtuple
import re


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

    relevant_order_lines = fields.Many2many(comodel_name='sale.order.line',
                                            store=False,
                                            compute='_compute_relevant_order_lines', )

    work_order_number = fields.Char(readonly=True)

    @api.model_create_multi
    def create(self, vals):
        res = super().create(vals)
        for rec in res:
            if rec.sale_order_id:
                seq = 1
                prev_seqs = self.sale_order_id.tasks_ids and \
                            self.sale_order_id.tasks_ids.mapped('work_order_number')
                if prev_seqs:
                    pattern = re.compile(r"\d+$")
                    matches = map(lambda n: pattern.search(n), prev_seqs)
                    seq += max(map(lambda n: int(n.group(1)) if n else 0), matches)
                rec.work_order_number = rec.sale_order_id.name.replace('SO', 'WO', 1) \
                                        + f"-{seq}"
        return res

    @api.depends('sale_order_id')
    def _compute_relevant_order_lines(self):
        for rec in self:
            rec.relevant_order_lines = (
                    rec.sale_order_id and rec.sale_order_id.get_relevant_order_lines(
                rec) or False)

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

    def action_fsm_validate(self):
        visits = self.filtered(lambda t: t.visit_id)
        non_visits = self - visits
        super(Task, non_visits).action_fsm_validate()

        visits._stop_all_timers_and_create_timesheets()
        closed_stage_by_project = visits._get_closed_stage_by_project()
        super(Task, visits.child_ids).action_fsm_validate()
        for visit in visits:
            stage = closed_stage_by_project[visit.project_id]
            visits.write({'stage_id': stage.id, 'fsm_done': True})

    def synchronize_name_fsm(self):
        """ Applies naming to the entire task tree for tasks that are part of this
        recordset. Root tasks are named:

            Partner Shipping Name - Sale Line Name (Template Name)

        Child tasks with sale_line_id are named by their template if set, sale line name
        if not.

        Child tasks not linked to sale lines are left with their original names."""

        all_tasks = self | self._get_all_subtasks()
        for rec in all_tasks:
            assert rec.is_fsm, "This method should only be called on FSM tasks."

            template = rec.sale_line_id and rec.sale_line_id.product_id.task_template_id
            name_parts = rec.sale_line_id and rec.sale_line_id.name.split('\n')
            title = name_parts and name_parts[0] or rec.sale_line_id.product_id.name
            if not rec.parent_id:
                rec.name = f"{rec.sale_order_id.partner_shipping_id.name} - " \
                           f"{title}"
                if template:
                    rec.name += f" ({template.name})"
            else:
                rec.name = template.name or title or rec.name

    @property
    def root_ancestor(self):
        return self.parent_id and self.parent_id.root_ancestor or self
