from odoo import fields, models


class MailConversationTag(models.Model):
    """Simple tag for classifying conversations."""

    _name = "mail.conversation.tag"
    _description = "Conversation Tag"
    _order = "name"

    name = fields.Char(required=True)
    color = fields.Integer()

    _sql_constraints = [
        ("name_uniq", "unique(name)", "A tag with this name already exists."),
    ]
