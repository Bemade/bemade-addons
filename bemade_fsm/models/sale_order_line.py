from odoo import fields, models, api, _, Command


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    valid_equipment_ids = fields.One2many(
        comodel_name="fsm.equipment", related="order_id.valid_equipment_ids"
    )

    visit_ids = fields.One2many(
        comodel_name="bemade_fsm.visit",
        inverse_name="so_section_id",
        string="Visits",
        copy=False,
    )

    visit_id = fields.Many2one(
        comodel_name="bemade_fsm.visit",
        compute="_compute_visit_id",
        string="Visit",
        ondelete="cascade",
        store=True,
    )

    is_fully_delivered = fields.Boolean(
        string="Fully Delivered",
        compute="_compute_is_fully_delivered",
        help=(
            "Indicates whether a line or all the lines in a section have been entirely"
            " delivered."
        ),
    )

    is_fully_delivered_and_invoiced = fields.Boolean(
        string="Fully Invoiced",
        compute="_compute_is_fully_invoiced",
        help=(
            "Indicates whether a line or all the lines in a section have been entirely"
            " delivered and invoiced."
        ),
    )

    equipment_ids = fields.Many2many(
        string="Equipment to Service",
        comodel_name="fsm.equipment",
        relation="bemade_fsm_equipment_sale_order_line_rel",
        column1="sale_order_line_id",
        column2="equipment_id",
    )

    is_field_service = fields.Boolean(compute="_compute_is_field_service", store=True)

    is_fsm = fields.Boolean(
        string="Is FSM",
        compute="_compute_is_fsm",
        store=True,
    )

    section_line_ids = fields.One2many(
        comodel_name="sale.order.line",
        compute="_compute_section_line_ids",
    )

    @api.depends("visit_ids")
    def _compute_visit_id(self):
        for rec in self:
            rec.visit_id = rec.visit_ids and rec.visit_ids[0]

    @api.depends("product_id")
    def _compute_is_field_service(self):
        for rec in self:
            rec.is_field_service = rec.product_id.is_field_service

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            if rec.order_id.default_equipment_ids and not rec.equipment_ids:
                rec.equipment_ids = rec.order_id.default_equipment_ids
        return recs

    def copy(self, default=None):
        new_line = super().copy(default)
        for visit in self.visit_ids:
            visit.copy({
                "so_section_id": new_line.id,
                "sale_order_id": new_line.order_id.id,
            })
        return new_line

    def _timesheet_create_task(self, project):
        """Generate task for the given so line, and link it.
                :param project: record of project.project in which the task should be created
                :return task: record of the created task

        Override to add the logic needed to implement task templates and equipment linkages.
        """

        def _create_task_from_template(project, template, parent):
            """Recursively generates the task and any subtasks from a project.task.template.

            :param project: project.project record to set on the task's project_id field.
            :param template: project.task.template to use to create the task.
            :param parent: project.task to set as the parent to this task.
            """
            values = _timesheet_create_task_prepare_values_from_template(
                project, template, parent
            )
            task = self.env["project.task"].sudo().create(values)
            subtasks = []
            for t in template.subtasks:
                subtask = _create_task_from_template(project, t, task)
                subtasks.append(subtask)

            # We don't want to see the sub-tasks on the SO
            if task.child_ids:
                task.child_ids.write(
                    {
                        "sale_order_id": None,
                        "sale_line_id": None,
                    }
                )

            return task

        def _timesheet_create_task_prepare_values_from_template(
            project, template, parent
        ):
            """Copies the values from a project.task.template over to the set of values used to create a project.task.

            :param project: project.project record to set on the task's project_id field.
                Pass the project.project model or an empty recordset to leave task project_id blank.
                DO NOT pass False or None as this will cause an error in _timesheet_create_task_prepare_values(project).
            :param template: project.task.template to use to create the task.
            :param parent: project.task to set as the parent to this task.
            """
            vals = self._timesheet_create_task_prepare_values(project)
            vals["name"] = template.name
            vals["description"] = (
                template.description or "" if parent else vals["description"]
            )
            vals["parent_id"] = parent and parent.id
            vals["user_ids"] = template.assignees.ids
            vals["tag_ids"] = template.tags.ids
            vals["allocated_hours"] = template.planned_hours
            vals["sequence"] = template.sequence
            # Use shipping address for FSM tasks for consistency
            if project and project.is_fsm:
                vals["partner_id"] = self.order_id.partner_shipping_id.id
            else:
                vals["partner_id"] = self.order_id.partner_id.id
            if template.equipment_ids:
                vals["equipment_ids"] = template.equipment_ids.ids
            return vals

        tmpl = self.product_id.task_template_id
        if not tmpl:
            task = super()._timesheet_create_task(project)
            # For FSM tasks without a template, update partner_id to use shipping address
            if project.is_fsm and task:
                task.partner_id = self.order_id.partner_shipping_id.id
        else:
            task = _create_task_from_template(project, tmpl, None)
            self.write({"task_id": task.id})
            # post message on task
            task_msg = _(
                "This task has been created from: <a href=# data-oe-model=sale.order"
                " data-oe-id=%(so_id)d>%(so_name)s</a> (%(product_name)s)"
            ) % {
                "so_id": self.order_id.id,
                "so_name": self.order_id.name,
                "product_name": self.product_id.name,
            }
            task.message_post(body=task_msg)

        if not task.equipment_ids and self.equipment_ids:
            task.equipment_ids = self.equipment_ids.ids
        return task

    def _timesheet_service_generation(self):
        super()._timesheet_service_generation()
        visit_lines = self.filtered(lambda line: line.visit_id)
        for index, line in enumerate(visit_lines):
            task_ids = line.get_section_line_ids().mapped("task_id")
            if not task_ids:
                continue
            if len(set([task.project_id for task in task_ids])) > 1:
                # Can't group up the tasks if they're part of different projects
                return
            project_id = task_ids[0].project_id
            line.visit_id.task_id = line._generate_task_for_visit_line(
                project_id, index + 1, sum(task_ids.mapped("allocated_hours"))
            )
            task_ids.write({"parent_id": line.visit_id.task_id.id})
        (self.mapped("task_id") | self.visit_ids.task_id).filtered(
            "is_fsm"
        ).synchronize_name_fsm()

    def _generate_task_for_visit_line(
        self, project, visit_no: int, allocated_hours: int
    ):
        self.ensure_one()

        allocated_hours = sum(
            self.get_section_line_ids().task_id.mapped("allocated_hours")
        )
        task = self.env["project.task"].create(
            {
                "name": (
                    f"{self.order_id.name} - "
                    + _("Visit")
                    + f" {visit_no} - {self.name}"
                ),
                "project_id": project.id,
                "equipment_ids": (
                    self.get_section_line_ids().mapped("equipment_ids").ids
                ),
                "sale_order_id": self.order_id.id,
                "partner_id": self.order_id.partner_shipping_id.id,
                "visit_id": self.visit_id.id,
                "allocated_hours": allocated_hours,
                "date_deadline": self.visit_id.approx_date,
                "user_ids": False,  # Force to empty or it uses the current user
            }
        )
        return task

    @api.depends(
        "order_id.order_line",
        "display_type",
        "qty_to_deliver",
        "order_id.order_line.qty_to_deliver",
        "order_id.order_line.display_type",
    )
    def _compute_is_fully_delivered(self):
        for rec in self:
            rec.is_fully_delivered = rec._iterate_items_compute_bool(
                lambda line: line.qty_to_deliver == 0
            )

    @api.depends("is_fully_delivered")
    def _compute_is_fully_invoiced(self):
        for rec in self:
            if rec.is_fully_delivered:
                rec.is_fully_delivered_and_invoiced = rec._iterate_items_compute_bool(
                    lambda line: line.qty_to_invoice == 0
                )
            else:
                rec.is_fully_delivered_and_invoiced = False

    def get_section_line_ids(self):
        """Return a recordset of sale.order.line records that are in this sale order section."""
        self.ensure_one()
        assert (
            self.display_type == "line_section"
        ), "Cannot get section lines for a non-section."
        found = False
        lines = []
        for line in self.order_id.order_line.sorted(lambda line: line.sequence):
            if line == self:
                found = True
                continue
            if not found:
                continue
            if line.display_type == "line_section":  # Stop when we hit the next section
                break
            else:
                lines.append(line)
        return self.env["sale.order.line"].union(*lines)

    @api.depends("display_type", "order_id.order_line")
    def _compute_section_line_ids(self):
        for rec in self:
            if rec.display_type == "line_section":
                rec.section_line_ids = [Command.set(rec.get_section_line_ids().ids)]
            else:
                rec.section_line_ids = False

    def _iterate_items_compute_bool(self, single_line_func):
        if not self.display_type:
            return single_line_func(self)
        elif self.display_type == "line_note":
            return True
        else:
            for line in self.order_id.order_line:
                found = False
                if line == self:
                    found = True
                if not found:
                    continue
                if found and line.display_type == "line_section":
                    return True
                val = single_line_func(self)
                if not val:
                    return val
            return True

    @api.depends("product_id.type", "product_id.service_tracking")
    def _compute_is_fsm(self):
        for rec in self:
            rec.is_fsm = (
                rec.product_id.type == "service"
                and rec.product_id.service_tracking == "task_global_project"
            )
