from odoo import api, fields, models


class MailConversationLink(models.Model):
    """Reifies the generic link between a conversation and a business
    record. Unlike native chatter (one ``res_model``/``res_id`` per
    thread), a conversation can be linked to any number of records, and a
    record can be the subject of any number of conversations -- this table
    is the join, enumerable from either side.
    """

    _name = "mail.conversation.link"
    _description = "Conversation Link"

    conversation_id = fields.Many2one(
        "mail.conversation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Many2oneReference(
        "Related Record ID",
        model_field="res_model",
        required=True,
        index=True,
    )
    reason = fields.Selection(
        [
            ("direct", "Direct"),
            ("reference", "Reference"),
            ("manual", "Manual"),
        ],
        default="direct",
        required=True,
    )

    _sql_constraints = [
        (
            "conversation_record_uniq",
            "unique(conversation_id, res_model, res_id)",
            "This conversation is already linked to this record.",
        ),
    ]

    @api.model
    def _conversations_for_record(self, res_model, res_id):
        """Enumerate the conversations linked to a given business record."""
        links = self.search(
            [("res_model", "=", res_model), ("res_id", "=", res_id)]
        )
        return links.conversation_id
