from odoo import fields, models


class MailConversationMember(models.Model):
    """Per-user triage state on a conversation (handled/unread/snoozed).
    Fully independent of the conversation's own ``state`` field: one
    member marking a conversation handled/read/snoozed for themselves has
    no effect on the conversation's team-level state, nor on any other
    member's state.
    """

    _name = "mail.conversation.member"
    _description = "Conversation Member"

    conversation_id = fields.Many2one(
        "mail.conversation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        required=True,
        index=True,
    )
    is_handled = fields.Boolean()
    unread = fields.Boolean()
    snooze_until = fields.Datetime()

    _sql_constraints = [
        (
            "conversation_user_uniq",
            "unique(conversation_id, user_id)",
            "This user is already a member of this conversation.",
        ),
    ]
