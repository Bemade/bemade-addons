from odoo import models, fields, api, _
from odoo.exceptions import UserError


class NewTaskFromTemplateWizard(models.TransientModel):
    _name = "project.task.from.template.wizard"
    _description = "Create Task from Template Wizard"

    project_id = fields.Many2one(
        comodel_name='project.project',
        string='Project',
        help='The project the new task should be created in.',
        required=True,
    )

    task_template_id = fields.Many2one(
        comodel_name='project.task.template',
        string='Task Template',
        help='The template to use when creating the new task.',
        required=True,
    )

    new_task_title = fields.Char(
        help='The title (name) for the newly created task. If left blank, the name of the template will be used.',
    )

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id', False)
        active_model = self.env.context.get('active_model', False)
        if not active_model:
            params = self.env.context.get('params', False)
            active_model = params and params.get('model', False)
        if active_model == 'project.task.template' and active_id and 'task_template_id' in fields_list:
            res.update({'task_template_id': active_id})
        if active_model == 'project.task' and 'project_id' in fields_list:
            res.update({'project_id': self.env.ref('industry_fsm.fsm_project').id})
        return res

    def action_create_task_from_template(self):
        self.ensure_one()
        task = self.task_template_id.create_task_from_self(self.project_id, self.new_task_title)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': task.id,
            'view_mode': 'form',
            'target': 'current',
        }


