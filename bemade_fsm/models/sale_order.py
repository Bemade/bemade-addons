from odoo import fields, models, api, _, Command
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    equipment_id = fields.Many2one(comodel_name="bemade_fsm.equipment",
                                   string="Equipment to Service",
                                   tracking=True,
                                   compute="_compute_equipment",
                                   inverse="_inverse_equipment",
                                   store=True)

    site_contacts = fields.Many2many(comodel_name='res.partner',
                                     relation="sale_order_site_contacts_rel",
                                     compute="_compute_default_contacts",
                                     inverse="_inverse_default_contacts",
                                     string='Site Contacts',
                                     store=True)

    work_order_contacts = fields.Many2many(comodel_name='res.partner',
                                           relation='sale_order_work_order_contacts_rel',
                                           compute='_compute_default_contacts',
                                           inverse='_inverse_default_contacts',
                                           string='Work Order Recipients',
                                           store=True)
    visit_ids = fields.One2many(comodel_name='bemade_fsm.visit',
                                inverse_name="sale_order_id",
                                readonly=False)

    @api.onchange('partner_shipping_id')
    def _onchange_partner_shipping_id(self):
        super()._onchange_partner_shipping_id()
        self._compute_equipment()
        self._compute_default_contacts()

    @api.depends('partner_shipping_id')
    def _compute_default_contacts(self):
        for rec in self:
            rec.site_contacts = rec.partner_shipping_id.site_contacts
            rec.work_order_contacts = rec.partner_shipping_id.work_order_contacts

    def _inverse_default_contacts(self):
        pass

    @api.depends('partner_shipping_id')
    def _compute_equipment(self):
        for rec in self:
            rec.equipment_id = self.partner_shipping_id.equipment_ids if len(
                self.partner_shipping_id.equipment_ids) <= 1 else False

    def _inverse_equipment(self):
        pass


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    visit_id = fields.One2many(comodel_name="bemade_fsm.visit",
                               inverse_name="so_section_id",
                               string="Visit")
    is_fully_delivered = fields.Boolean(string="Fully Delivered",
                                        compute="_compute_is_fully_delivered",
                                        help="Indicates whether a line or all the lines in a section have been"
                                             "entirely delivered.")
    is_fully_delivered_and_invoiced = fields.Boolean(string="Fully Invoiced",
                                       compute="_compute_is_fully_invoiced",
                                       help="Indicates whether a line or all the lines in a section have been"
                                            "entirely delivered and invoiced.")

    def _timesheet_create_task(self, project):
        """ Generate task for the given so line, and link it.
                    :param project: record of project.project in which the task should be created
                    :return task: record of the created task

            Override to add the logic needed to implement task templates and equipment linkages."""

        def _create_task_from_template(project, template, parent):
            """ Recursively generates the task and any subtasks from a project.task.template.

            :param project: project.project record to set on the task's project_id field.
            :param template: project.task.template to use to create the task.
            :param parent: project.task to set as the parent to this task.
            """
            values = _timesheet_create_task_prepare_values_from_template(project, template, parent)
            task = self.env['project.task'].sudo().create(values)
            subtasks = []
            for t in template.subtasks:
                subtask = _create_task_from_template(project, t, task)
                subtasks.append(subtask)
            task.write({'child_ids': [Command.set([t.id for t in subtasks])]})
            # We don't want to see the sub-tasks on the SO
            task.child_ids.write({'sale_order_id': None, 'sale_line_id': None, })
            return task

        def _generate_task_name(template=None):
            template_name = template and template.name
            return f"{self.order_id.name}: {self.order_id.partner_shipping_id.name} - {self.name} ({template_name})"

        def _timesheet_create_task_prepare_values_from_template(project, template, parent):
            """ Copies the values from a project.task.template over to the set of values used to create a project.task.

            :param project: project.project record to set on the task's project_id field.
                Pass the project.project model or an empty recordset to leave task project_id blank.
                DO NOT pass False or None as this will cause an error in _timesheet_create_task_prepare_values(project).
            :param template: project.task.template to use to create the task.
            :param parent: project.task to set as the parent to this task.
            """
            vals = self._timesheet_create_task_prepare_values(project)
            vals['name'] = _generate_task_name(template) if not parent else template.name
            vals['description'] = template.description or vals['description']
            vals['parent_id'] = parent and parent.id
            vals['user_ids'] = template.assignees.ids
            vals['tag_ids'] = template.tags.ids
            vals['planned_hours'] = template.planned_hours
            if template.equipment_id:
                vals['equipment_ids'] = [Command.set([template.equipment_id.id])]
            return vals

        tmpl = self.product_id.task_template_id
        if not tmpl:
            task = super()._timesheet_create_task(project)
        else:
            task = _create_task_from_template(project, tmpl, None)
            self.write({'task_id': task.id})
            # post message on task
            task_msg = _(
                "This task has been created from: <a href=# data-oe-model=sale.order data-oe-id=%d>%s</a> (%s)") % (
                           self.order_id.id, self.order_id.name, self.product_id.name)
            task.message_post(body=task_msg)
        if not task.equipment_ids and self.order_id.equipment_id:
            task.write({'equipment_ids': [Command.set([self.order_id.equipment_id.id])]})
        task.name = _generate_task_name(tmpl)
        return task

    @api.depends('order_id.order_line', 'display_type', 'qty_to_deliver', 'order_id.order_line.qty_to_deliver',
                 'order_id.order_line.display_type')
    def _compute_is_fully_delivered(self):
        self.is_fully_delivered = self._iterate_items_compute_bool(lambda l: l.qty_to_deliver == 0)

    @api.depends('is_fully_delivered')
    def _compute_is_fully_invoiced(self):
        if not self.is_fully_delivered:
            self.is_fully_delivered_and_invoiced = False
            return
        self.is_fully_delivered_and_invoiced = self._iterate_items_compute_bool(lambda l: l.qty_to_invoice == 0)

    def _iterate_items_compute_bool(self, single_line_func):
        if not self.display_type:
            return single_line_func(self)
        elif self.display_type == 'line_note':
            return True
        else:
            for line in self.order_id.order_line:
                found = False
                if line == self:
                    found = True
                if not found:
                    continue
                if found and line.display_type == 'line_section':
                    return True
                val = single_line_func(self)
                if not val:
                    return val
            return True
