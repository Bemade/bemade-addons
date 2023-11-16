from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    task_template_id = fields.Many2one(
        comodel_name="project.task.template",
        string="Task Template",
        ondelete='restrict'
    )

    is_field_service = fields.Boolean(
        string="Plan as field service",
        help="Products planned as field service will have travel time considered in planning."
    )
