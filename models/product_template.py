from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    task_template_id = fields.Many2one("project.task.template", string="Task Template", ondelete='restrict')
