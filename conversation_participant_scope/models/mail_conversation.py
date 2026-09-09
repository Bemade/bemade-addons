from odoo import fields, models


class MailConversation(models.Model):
    """Adds conversation-level roster policy plus helpers to add/find
    participants with the scope fields shipped by this module,
    compute the participant/CC list visible to a given viewer, and
    compute who should receive the next outbound message.
    """

    _inherit = "mail.conversation"

    external_visibility = fields.Selection(
        [
            ("hide_internal", "Hide internal team from externals"),
            ("full", "All participants visible"),
            ("private", "Each external sees only themselves"),
        ],
        default="hide_internal",
        required=True,
        help="Conversation-level policy controlling what an external "
        "viewer sees of the participant/CC list. Per-participant "
        "visibility overrides (mail.conversation.participant.visibility) "
        "are applied on top of this base policy.",
    )

    def _add_participant(
        self,
        email=None,
        partner=None,
        kind="external",
        role="to",
        receives_updates=True,
        visibility="auto",
    ):
        """Add (or find) a participant on this conversation and apply
        the scope fields shipped by this module. Thin wrapper over the
        base ``mail.conversation.participant._get_or_create``, so a
        bare ``email`` with no ``partner`` never creates a res.partner
        and adding a participant never calls ``message_subscribe``
        (see conversation_base).
        """
        self.ensure_one()
        if not email and not partner:
            raise ValueError(
                "_add_participant requires at least one of email or partner"
            )
        if not email:
            email = partner.email
        participant = self.env["mail.conversation.participant"]._get_or_create(
            self, email, partner=partner or False
        )
        participant.write(
            {
                "kind": kind,
                "role": role,
                "receives_updates": receives_updates,
                "visibility": visibility,
            }
        )
        return participant

    def _add_cc_once(self, emails=(), partners=()):
        """Add one-off CC participants: included on the next outbound
        message only, excluded from future recipient computation
        (``receives_updates=False``) until explicitly promoted via
        ``mail.conversation.participant._promote_to_recipient``.
        """
        self.ensure_one()
        participants = self.env["mail.conversation.participant"]
        for email in emails:
            participants |= self._add_participant(
                email=email, role="cc", receives_updates=False
            )
        for partner in partners:
            participants |= self._add_participant(
                partner=partner, role="cc", receives_updates=False
            )
        return participants

    def _participants_visible_to(self, viewer):
        """Return the participant recordset ``viewer`` (a res.partner,
        or a falsy value for an internal/system viewer) may see of
        this conversation's participant/CC list.

        Internal viewers (no viewer, or a viewer partner linked to an
        internal user) see everyone. External viewers see a base set
        determined by ``external_visibility``, then per-participant
        ``visibility`` overrides are applied last: ``exposed`` force-adds
        a participant even to fellow externals, ``hidden`` force-removes
        one even from the viewer's own visible set.
        """
        self.ensure_one()
        all_participants = self.participant_ids
        is_internal_viewer = not viewer or bool(
            self.env["res.users"]
            .sudo()
            .search([("partner_id", "=", viewer.id)], limit=1)
        )
        if is_internal_viewer:
            base = all_participants
        elif self.external_visibility == "full":
            base = all_participants
        elif self.external_visibility == "private":
            base = all_participants.filtered(lambda p: p.partner_id == viewer)
        else:  # 'hide_internal', the default
            base = all_participants.filtered(lambda p: p.kind == "external")

        exposed = all_participants.filtered(lambda p: p.visibility == "exposed")
        hidden = all_participants.filtered(lambda p: p.visibility == "hidden")
        return (base | exposed) - hidden

    def _next_message_recipients(self):
        """Return ``(partners, email_to)`` for the next outbound
        message: ``partners`` is the res.partner recordset of
        participants with ``receives_updates=True`` and a linked
        ``partner_id``; ``email_to`` is the list of ``email_normalized``
        for ``receives_updates=True`` bare-email (no ``partner_id``)
        participants. CC-once participants (``receives_updates=False``)
        are excluded from both.
        """
        self.ensure_one()
        active = self.participant_ids.filtered("receives_updates")
        partners = active.filtered("partner_id").mapped("partner_id")
        email_to = active.filtered(lambda p: not p.partner_id).mapped(
            "email_normalized"
        )
        return partners, email_to
