from odoo import api, fields, models, tools


class MailConversationParticipant(models.Model):
    """Who is on a conversation -- a partner, a bare email address, or
    both. Deliberately separate from ``mail.followers``: adding a
    participant never subscribes anyone (no ``message_subscribe`` call
    anywhere in this model), so conversation participation and chatter
    notification stay independent concerns.
    """

    _name = "mail.conversation.participant"
    _description = "Conversation Participant"

    conversation_id = fields.Many2one(
        "mail.conversation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        help="Optional: a bare email address without a matching partner is "
        "a valid participant on its own.",
    )
    email = fields.Char()
    email_normalized = fields.Char(
        compute="_compute_email_normalized",
        store=True,
        index=True,
        help="Normalized email, used as the bare-email match/dedup key. "
        "NULL (not an empty string) when the participant has no address, "
        "so that the plain unique(conversation_id, email_normalized) "
        "constraint lets partner-only participants coexist freely "
        "(Postgres treats NULLs as distinct) while still deduping "
        "non-null emails per conversation.",
    )
    kind = fields.Selection(
        [
            ("external", "External"),
            ("internal", "Internal"),
        ],
        default="external",
        required=True,
    )
    role = fields.Selection(
        [
            ("to", "To"),
            ("cc", "Cc"),
            ("requester", "Requester"),
            ("watcher", "Watcher"),
        ],
        default="to",
        required=True,
    )

    _sql_constraints = [
        (
            "conversation_partner_uniq",
            "unique(conversation_id, partner_id)",
            "This partner is already a participant on this conversation.",
        ),
        (
            "conversation_email_uniq",
            "unique(conversation_id, email_normalized)",
            "This email address is already a participant on this conversation.",
        ),
    ]

    @api.depends("partner_id", "partner_id.email_normalized", "email")
    def _compute_email_normalized(self):
        for participant in self:
            if participant.partner_id:
                participant.email_normalized = (
                    participant.partner_id.email_normalized or False
                )
            else:
                participant.email_normalized = (
                    tools.email_normalize(participant.email) or False
                )

    @api.model
    def _get_or_create(self, conversation, email, partner=False, role=False):
        """Find or create the participant for ``email`` (bare-email,
        dedup'd on ``email_normalized``) on ``conversation``. If
        ``partner`` is passed and the existing participant has no
        ``partner_id`` yet, link it lazily. ``role`` (to/cc/requester/
        watcher) only seeds a *new* participant -- an existing
        participant's role is never overwritten by a later call (e.g. a
        watcher promoted to requester on a follow-up should be a deliberate
        action, not an ETL side effect). Never calls ``message_subscribe``
        -- see class docstring.
        """
        normalized = tools.email_normalize(email) or False
        participant = self.search(
            [
                ("conversation_id", "=", conversation.id),
                ("email_normalized", "=", normalized),
            ],
            limit=1,
        )
        if participant:
            if partner and not participant.partner_id:
                participant.partner_id = partner
            return participant
        values = {
            "conversation_id": conversation.id,
            "email": email,
            "partner_id": partner.id if partner else False,
        }
        if role:
            values["role"] = role
        return self.create(values)

    @api.model
    def _conversations_for_partner(self, partner):
        """Enumerate the conversations a partner participates in."""
        participants = self.search([("partner_id", "=", partner.id)])
        return participants.conversation_id
