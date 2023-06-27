from odoo import models, fields, api, _


class TaskTemplate(models.Model):
    _name = 'project.task.template'
    _description = "Template for new project tasks"
    @api.model
    def _current_company(self):
        return self.env.company

    name = fields.Char(string="Task Title", required=True)
    description = fields.Html(string="Description")
    assignees = fields.Many2many("res.users", string="Default Assignees", help="Employees assigned to tasks created from this template.")
    customer = fields.Many2one("res.partner", string="Default Customer", help="Default customer for tasks created from this template.")
    project = fields.Many2one("project.project", string="Default Project", help="Default project for tasks created from this template.")
    tags = fields.Many2many("project.tags", string="Default Tags", help="Default tags for tasks created from this template.")
    parent = fields.Many2one("project.task.template", string="Parent Task Template", ondelete='cascade')
    subtasks = fields.One2many("project.task.template", inverse_name="parent", string="Subtask Templates")
    sequence = fields.Integer(string="Sequence")
    company_id = fields.Many2one("res.company", string="Company", index=1, default=_current_company)
    planned_hours = fields.Float("Initially Planned Hours")

    def action_open_task(self):
        return {
            'view_mode': 'form',
            'res_model': 'project.task.template',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'context': self._context
        }


