from odoo import fields, models, api, Command
from odoo.addons.project.models.project_task import CLOSED_STATES
import re
from typing import cast, List


class Task(models.Model):
    _inherit = "project.task"

    work_order_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="task_work_order_contact_rel",
        column1="task_id",
        column2="res_partner_id",
    )

    site_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="task_site_contact_rel",
        column1="task_id",
        column2="res_partner_id",
    )

    # Override related field to make it return false if this is an FSM subtask
    allow_billable = fields.Boolean(
        string="Can be billed",
        related=False,
        compute="_compute_allow_billable",
        store=True,
    )

    visit_id = fields.Many2one(
        comodel_name="bemade_fsm.visit",
        string="Visit",
    )

    relevant_order_lines = fields.Many2many(
        comodel_name="sale.order.line",
        store=False,
        compute="_compute_relevant_order_lines",
    )

    work_order_number = fields.Char(readonly=True)

    propagate_assignment = fields.Boolean(
        help="Propagate assignment of this task to all subtasks.",
        default=False,
    )

    is_closed = fields.Boolean(
        compute="_compute_is_closed",
    )

    root_ancestor = fields.Many2one(
        comodel_name="project.task",
        compute="_compute_root_ancestor",
        recursive=True,
    )

    template_id = fields.Many2one(
        comodel_name="project.task.template",
        string="From Template",
        store=False,
        copy=False,
    )

    def _apply_template_to_self(self, template=None):
        """Apply a task template to this task record.

        Fills the task with the template's field values (name, description,
        assignees, tags, hours, equipment, …) IN PLACE, then instantiates
        only the template's child templates as subtasks (grandchildren are
        created recursively by create_task_from_self). The row's own template
        is NOT passed to create_task_from_self — the row was already created by
        super().create; we merely populate it and hang children beneath it.

        :param template: the project.task.template to apply. When omitted, the
            value carried on ``self.template_id`` is used. The create/write
            overrides pass the template explicitly because ``template_id`` is a
            non-stored field, so the ORM does not retain its value in the record
            cache after ``super().create()`` / ``super().write()``.
        """
        self.ensure_one()
        if template is None:
            template = self.template_id
        if not template:
            return

        # Resolve project: prefer the row's own project_id, fall back to parent's.
        project = self.project_id or self.parent_id.project_id
        if not project:
            # Cannot instantiate without a project; skip defensively.
            return

        # Build the template's value dict, then strip structural keys that the
        # row already has set correctly (per design-reviewer refinement #1).
        vals = template._prepare_new_task_values_from_self(
            project, parent_id=self.parent_id.id or False
        )
        vals.pop("parent_id", None)
        vals.pop("project_id", None)

        self.write(vals)

        # Instantiate only the child templates; recursion to grandchildren is
        # handled inside create_task_from_self (task_template.py:120).
        if template.subtasks:
            template.subtasks.create_task_from_self(project, parent_id=self.id)

    def _compute_is_closed(self):
        for rec in self:
            rec.is_closed = rec.state in CLOSED_STATES

    @api.model_create_multi
    def create(self, vals_list):
        # Capture template_id from the incoming vals: it is a non-stored field,
        # so the ORM drops it from the record cache after super().create() and
        # we cannot read it back off the created record.
        template_ids = [vals.get("template_id") for vals in vals_list]
        res = super().create(vals_list)
        for rec, template_id in zip(res, template_ids):
            if template_id:
                rec._apply_template_to_self(
                    self.env["project.task.template"].browse(template_id)
                )
            if rec.parent_id and rec.is_fsm:
                # Always ensure FSM subtasks have a partner_id set from their parent
                rec.partner_id = rec.parent_id.partner_id
                if not rec.work_order_contacts and rec.parent_id:
                    rec.work_order_contacts = rec.parent_id.work_order_contacts
                if not rec.site_contacts and rec.parent_id:
                    rec.site_contacts = rec.parent_id.site_contacts
            if rec.sale_order_id:
                seq = 1
                prev_seqs = (
                    self.sale_order_id.tasks_ids
                    and self.sale_order_id.tasks_ids.mapped("work_order_number")
                )
                if prev_seqs:
                    pattern = re.compile(r"(\d+)$")
                    matches = map(
                        lambda n: pattern.search(n), cast(List[str], prev_seqs)
                    )
                    seq += max(map(lambda n: int(n.group(1)) if n else 0, matches))
                rec.work_order_number = (
                    rec.sale_order_id.name.replace("SO", "SVR", 1) + f"-{seq}"
                )
                # If the task is linked to a sales order and has no parent, it should inherit SO work order contacts
                if (
                    not rec.parent_id
                    and not rec.work_order_contacts
                    and rec.sale_order_id.work_order_contacts
                ):
                    rec.work_order_contacts = rec.sale_order_id.work_order_contacts
                if (
                    not rec.parent_id
                    and not rec.site_contacts
                    and rec.sale_order_id.site_contacts
                ):
                    rec.site_contacts = rec.sale_order_id.site_contacts
        return res

    def write(self, vals):
        res = super().write(vals)
        if not self:  # End recursion on empty RecordSet
            return res
        if vals.get("template_id"):
            # template_id was set on one or more existing rows — apply it to
            # each. Read the id from vals (non-stored field, dropped from cache).
            template = self.env["project.task.template"].browse(vals["template_id"])
            for rec in self:
                rec._apply_template_to_self(template)
        if "propagate_assignment" in vals:
            # When a user sets propagate assignment, it should propagate that setting all the way down the chain
            self.child_ids.write({"propagate_assignment": vals["propagate_assignment"]})
        if "user_ids" in vals:
            to_propagate = self.filtered(lambda task: task.propagate_assignment)
            # Here we use child_ids instead of _get_all_subtasks() so as to allow for setting propagate_assignment
            # to false on a child task.
            to_propagate.child_ids.write({"user_ids": vals["user_ids"]})
        for rec in self:
            if rec.child_ids:
                child_vals = {}
                if "site_contacts" in vals:
                    child_vals.update(
                        site_contacts=[Command.set(rec.site_contacts.ids)]
                    )
                if "work_order_contacts" in vals:
                    child_vals.update(
                        work_order_contacts=[Command.set(rec.work_order_contacts.ids)]
                    )
                if "partner_id" in vals:
                    child_vals.update(partner_id=vals["partner_id"])
                if "state" in vals and rec.state in CLOSED_STATES:
                    # Propagate task completion or cancelling to subtasks
                    child_vals.update(state=rec.state)
                if child_vals:
                    rec.child_ids.write(child_vals)
        date_keys = ["planned_date_begin", "date_deadline"]
        keys_to_propagate = [k for k in date_keys if k in vals]
        if keys_to_propagate:
            for rec in self.filtered("is_fsm"):
                date_vals = {k: getattr(rec, k) for k in keys_to_propagate}
                all_children = rec._get_all_subtasks()
                if all_children:
                    all_children.write(date_vals)
        return res

    @api.depends("sale_order_id")
    def _compute_relevant_order_lines(self):
        for rec in self:
            rec.relevant_order_lines = (
                rec.sale_order_id
                and rec.sale_order_id.get_relevant_order_lines(rec)
                or False
            )

    @api.depends("parent_id.visit_id", "project_id.is_fsm", "project_id.allow_billable")
    def _compute_allow_billable(self):
        for rec in self:
            # If an FSM task has a parent that is linked to an SO line, then the parent is the billable one
            if (
                rec.parent_id
                and not rec.parent_id.visit_id
                and rec.project_id
                and rec.project_id.is_fsm
            ):
                rec.allow_billable = False
            else:
                rec.allow_billable = rec.project_id.allow_billable

    def _fsm_create_sale_order_line(self):
        # Override to not generate new lines for tasks that are just linked to a visit item
        self.ensure_one()
        if self.visit_id:
            return
        else:
            super()._fsm_create_sale_order_line()

    def action_fsm_validate(self, stop_running_timers=False):
        # Override to close out subtasks as well
        all_tasks = self | self._get_all_subtasks()
        return super(Task, all_tasks).action_fsm_validate(stop_running_timers)

    def _get_full_hierarchy(self):
        if self.child_ids:
            return self | self.child_ids._get_full_hierarchy()
        return self

    def synchronize_name_fsm(self):
        """Applies naming to the entire task tree for tasks that are part of this
        recordset. Root tasks are named:

            Partner Shipping Name - Sale Line Name (Template Name)

        Child tasks with sale_line_id are named by their template if set, sale line name
        if not.

        Child tasks not linked to sale lines are left with their original names."""

        all_tasks = self | self._get_all_subtasks()
        for rec in all_tasks:
            assert rec.is_fsm, "This method should only be called on FSM tasks."

            template = rec.sale_line_id and rec.sale_line_id.product_id.task_template_id

            if template:
                title = template.name
            elif rec.sale_line_id:
                name_parts = rec.sale_line_id.name.split("\n")
                title = name_parts and name_parts[0] or rec.sale_line_id.product_id.name
            elif rec.visit_id:
                title = rec.visit_id.label
            else:
                rec.name = rec.name
                return

            client_name = rec.sale_order_id.partner_shipping_id.name

            if not rec.parent_id:
                rec.name = f"{rec.work_order_number} - {client_name} - {title}"
            else:
                rec.name = title

    @api.depends("parent_id", "parent_id.root_ancestor")
    def _compute_root_ancestor(self):
        for rec in self:
            rec.root_ancestor = rec.parent_id and rec.parent_id.root_ancestor or self

    @api.depends(
        "sale_line_id.order_partner_id",
        "parent_id.sale_line_id",
        "project_id.sale_line_id",
        "milestone_id.sale_line_id",
        "allow_billable",
    )
    def _compute_sale_line(self):
        """Override to prevent subtasks from inheriting parent's sale_line_id.

        In the base implementation, if a task and its parent share the same commercial partner,
        the task will inherit the parent's sale_line_id. This causes issues with our FSM tasks
        where we explicitly want subtasks to NOT have a sale_line_id set.
        """

        # Only run on root tasks
        subtasks = self.filtered("parent_id")
        (subtasks - subtasks.filtered("sale_line_id")).sale_line_id = False
        super(Task, self - subtasks)._compute_sale_line()

    @api.depends("parent_id.partner_id", "project_id")
    def _compute_partner_id(self):
        """Override to prevent clearing partner_id for FSM tasks.

        In the base implementation, if a task has a partner_id but no project_id or parent_id,
        the partner_id is cleared. This causes issues with our FSM tasks where we want to
        preserve the partner_id even if project_id or parent_id is temporarily not set.
        """
        # Only run the standard logic on non-FSM tasks
        non_fsm_tasks = self.filtered(lambda t: not t.is_fsm)
        super(Task, non_fsm_tasks)._compute_partner_id()

        # For FSM tasks, only set partner_id if it's not already set
        fsm_tasks = self - non_fsm_tasks
        for task in fsm_tasks:
            if not task.partner_id:
                task.partner_id = self._get_default_partner_id(
                    task.project_id, task.parent_id
                )
