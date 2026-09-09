from odoo import models, fields


class FSMTaskClientRequirement(models.Model):
    """Client-facing requirements that can be communicated in visit confirmation emails.

    This model stores reusable requirement types (e.g., "Water Shutdown Required",
    "Power Shutdown Required", etc.) that can be linked to tasks.

    New requirements can be added via the UI without code changes.
    """
    _name = "fsm.task.client.requirement"
    _description = "FSM Task Client Requirement"

    name = fields.Char(
        string="Requirement Name",
        required=True,
        translate=True,
        help="The name displayed to the client (e.g., 'Water Shutdown Required').",
    )
    description = fields.Text(
        string="Description",
        help="Additional information shown to the client when this requirement applies.",
    )
    active = fields.Boolean(default=True)
    color = fields.Integer(
        string="Color Index",
        default=0,
        help="Color for kanban/tags display.",
    )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name)", "Requirement name must be unique."),
    ]