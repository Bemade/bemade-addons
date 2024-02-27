from odoo import fields, models, api, Command, _
from odoo.exceptions import ValidationError, UserError
from odoo.osv import expression
from collections import defaultdict, namedtuple
import re


class Task(models.Model):
    _inherit = "project.task"

    equipment_ids = fields.Many2many(
        comodel_name="bemade_fsm.equipment",
        relation="bemade_fsm_task_equipment_rel",
        column1="task_id",
        column2="equipment_id",
        string="Equipment to Service",
        tracking=True,
    )

    work_order_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="task_work_order_contact_rel",
        column1="task_id",
        column2="res_partner_id",
        compute="_compute_contacts",
        inverse="_inverse_contacts",
        store=True
    )

    site_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="task_site_contact_rel",
        column1="task_id",
        column2="res_partner_id",
        compute="_compute_contacts",
        inverse="_inverse_contacts",
        store=True
    )

    # planned_date_begin = fields.Datetime(
    #     string="Planned Start Date",
    #     tracking=True,
    #     task_dependency_tracking=True,
    #     compute="_compute_planned_dates",
    #     inverse="_inverse_planned_dates",
    #     store=True
    # )
    #
    # planned_date_end = fields.Datetime(
    #     string="Planned End Date",
    #     tracking=True,
    #     task_dependency_tracking=True,
    #     compute="_compute_planned_dates",
    #     inverse="_inverse_planned_dates",
    #     store=True
    # )

    # Override related field to make it return false if this is an FSM subtask
    allow_billable = fields.Boolean(
        string="Can be billed",
        related=False,
        compute="_compute_allow_billable",
        store=True
    )

    visit_id = fields.Many2one(
        comodel_name='bemade_fsm.visit',
        string="Visit",
    )

    relevant_order_lines = fields.Many2many(
        comodel_name='sale.order.line',
        store=False,
        compute='_compute_relevant_order_lines',
    )

    work_order_number = fields.Char(readonly=True)

    propagate_assignment = fields.Boolean(
        string='Propagate Assignment',
        help='Propagate assignment of this task to all subtasks.',
        default=False,
    )

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
                rec.work_order_number = rec.sale_order_id.name.replace('SO', 'SVR', 1) \
                                        + f"-{seq}"
        return res

    def write(self, vals):
        super().write(vals)
        if not self:  # End recursion on empty RecordSet
            return
        if 'propagate_assignment' in vals:
            # When a user sets propagate assignment, it should propagate that setting all the way down the chain
            self.child_ids.write({'propagate_assignment': vals['propagate_assignment']})
        if 'user_ids' in vals:
            to_propagate = self.filtered(lambda task: task.propagate_assignment)
            # Here we use child_ids instead of _get_all_subtasks() so as to allow for setting propagate_assignment
            # to false on a child task.
            to_propagate.child_ids.write({'user_ids': vals['user_ids']})

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

    # def _get_related_planning_slots(self):
    #     domain = [('task_id', 'in', self.ids + self._get_all_subtasks().ids), ('start_datetime', '!=', False)]
    #     return self.env['planning.slot'].search(domain)

    # @api.depends('planned_hours')
    # def _compute_planned_dates(self):
    #     forecast_data = self._get_related_planning_slots()
    #     mapped_data = {}
    #     TimeSpan = namedtuple('timespan', ['start', 'end'])
    #     for d in forecast_data:
    #         if d not in mapped_data:
    #             mapped_data.update({d: TimeSpan(d.start_datetime, d.end_datetime)})
    #             continue
    #         if mapped_data[d].start > d.start_datetime:
    #             mapped_data[d].start = d.start_datetime
    #         if mapped_data[d].end < d.end_datetime:
    #             mapped_data[d].end = d.end_datetime
    #     for rec in self:
    #         if rec not in mapped_data:
    #             if not rec.planned_date_end:
    #                 rec.planned_date_end = False
    #             if not rec.planned_date_begin:
    #                 rec.planned_date_begin = False
    #             continue
    #         rec.planned_date_begin, rec.planned_date_end = mapped_data[rec]
    #
    # def _inverse_planned_dates(self):
    #     """ Modifying the planned dates for tasks with existing planning records
    #     (planning.slot) has no defined safe behaviour, so we block it."""
    #     if self._get_related_planning_slots():
    #         raise UserError(_("Modifying the planned start or end time on a task is not "
    #                           "permitted when that task already has planning records "
    #                           "associated to it. Please modify or delete the planning "
    #                           "records instead."))

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

    def action_fsm_validate(self, stop_running_timers=False):
        all_tasks = self | self._get_all_subtasks()
        non_visit_tasks = all_tasks.filtered(lambda task: not task.visit_id)
        visit_tasks = all_tasks.filtered(lambda task: bool(task.visit_id))
        result = visit_tasks._validate_task_without_creating_sale_order_line(stop_running_timers)
        if isinstance(result, dict):
            return result
        result = super(Task, non_visit_tasks).action_fsm_validate(stop_running_timers)
        if isinstance(result, dict):
            return result
        return result

    def _validate_task_without_creating_sale_order_line(self, stop_running_timers=False):
        # Reproduce the functionality of action_fsm_validate but don't apply logic from industry_fsm_sale
        # so as to avoid creating order lines for visits
        Timer = self.env['timer.timer']
        tasks_running_timer_ids = Timer.search([('res_model', '=', 'project.task'), ('res_id', 'in', self.ids)])
        timesheets = self.env['account.analytic.line'].sudo().search([('task_id', 'in', self.ids)])
        timesheets_running_timer_ids = None
        if timesheets:
            timesheets_running_timer_ids = Timer.search([
                ('res_model', '=', 'account.analytic.line'),
                ('res_id', 'in', timesheets.ids)])
        if tasks_running_timer_ids or timesheets_running_timer_ids:
            if stop_running_timers:
                self._stop_all_timers_and_create_timesheets(tasks_running_timer_ids, timesheets_running_timer_ids,
                                                            timesheets)
            else:
                wizard = self.env['project.task.stop.timers.wizard'].create({
                    'line_ids': [Command.create({'task_id': task.id}) for task in self],
                })
                return {
                    'name': _('Do you want to stop the running timers?'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'view_id': self.env.ref('industry_fsm.view_task_stop_timer_wizard_form').id,
                    'target': 'new',
                    'res_model': 'project.task.stop.timers.wizard',
                    'res_id': wizard.id,
                }
        closed_stage_by_project = {
            project.id:
                project.type_ids.filtered(lambda stage: stage.fold)[:1] or project.type_ids[-1:]
            for project in self.project_id
        }
        for task in self:
            # determine closed stage for task
            closed_stage = closed_stage_by_project.get(self.project_id.id)
            values = {'fsm_done': True}
            if closed_stage:
                values['stage_id'] = closed_stage.id

            task.write(values)

    def _get_full_hierarchy(self):
        if self.child_ids:
            return self | self.child_ids._get_full_hierarchy()
        return self

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
