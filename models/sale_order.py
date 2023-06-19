from odoo import fields, models, api, _, Command


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _timesheet_create_task(self, project):
        """ Generate task for the given so line, and link it.
                    :param project: record of project.project in which the task should be created
                    :return task: record of the created task

            Override to add the logic needed to implement task templates."""

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

        def _timesheet_create_task_prepare_values_from_template(project, template, parent):
            """ Copies the values from a project.task.template over to the set of values used to create a project.task.

            :param project: project.project record to set on the task's project_id field.
                Pass the project.project model or an empty recordset to leave task project_id blank.
                DO NOT pass False or None as this will cause an error in _timesheet_create_task_prepare_values(project).
            :param template: project.task.template to use to create the task.
            :param parent: project.task to set as the parent to this task.
            """
            vals = self._timesheet_create_task_prepare_values(project)
            vals['name'] = f"{vals['name']} ({template.name})" if not parent else template.name
            vals['description'] = template.description or vals['description']
            vals['parent_id'] = parent and parent.id
            vals['user_ids'] = template.assignees.ids
            vals['tag_ids'] = template.tags.ids
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
        return task
