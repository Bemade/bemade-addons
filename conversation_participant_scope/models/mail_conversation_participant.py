from odoo import fields, models


class MailConversationParticipant(models.Model):
    """Adds a per-conversation, per-participant scope: whether a
    participant is an ongoing recipient of future messages or a
    one-off CC, and an override of the conversation's external
    visibility policy for this one participant.
    """

    _inherit = "mail.conversation.participant"

    receives_updates = fields.Boolean(
        default=True,
        help="True: an ongoing member of this conversation's audience, "
        "included in future outbound recipient computation. False: a "
        "one-off CC included on a single message only -- excluded from "
        "future recipient computation until promoted (see "
        "_promote_to_recipient).",
    )
    visibility = fields.Selection(
        [
            ("auto", "Follow conversation policy"),
            ("exposed", "Always visible to externals"),
            ("hidden", "Hidden from externals"),
        ],
        default="auto",
        required=True,
        help="Per-participant override of the conversation's "
        "external_visibility policy, applied last when computing what "
        "an external viewer may see of the participant/CC list.",
    )

    def _promote_to_recipient(self):
        """Turn a one-off CC participant into an ongoing recipient of
        future messages on this conversation. Idempotent; never calls
        ``message_subscribe`` -- see the base class docstring.
        """
        for participant in self:
            if not participant.receives_updates:
                participant.receives_updates = True
