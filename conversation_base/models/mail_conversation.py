import ast

from markupsafe import Markup

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError


class MailConversation(models.Model):
    """A first-class conversation: the triage unit. Independent of any
    single business record -- see ``mail.conversation.link`` for the
    reified, many-to-many relationship to the records a conversation is
    about.

    Owns its messages the ordinary Odoo way (``mail.message.model ==
    'mail.conversation'``, ``res_id == conversation.id``) via
    ``mail.thread``.
    """

    _name = "mail.conversation"
    _description = "Conversation"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "mail.alias.mixin",
    ]
    _order = "id desc"

    name = fields.Char(
        required=True,
        tracking=True,
        help="The conversation's subject/title, used for triage. There is "
        "deliberately no separate 'subject' field: per-message subjects "
        "stay native on mail.message.",
    )
    state = fields.Selection(
        [
            ("open", "Open"),
            ("snoozed", "Snoozed"),
            ("waiting", "Waiting"),
            ("done", "Done"),
        ],
        default="open",
        required=True,
        tracking=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Assignee",
        tracking=True,
    )
    team_id = fields.Many2one(
        "mail.conversation.team",
        string="Team",
        tracking=True,
    )
    tag_ids = fields.Many2many(
        "mail.conversation.tag",
        "mail_conversation_tag_rel",
        "conversation_id",
        "tag_id",
        string="Tags",
    )
    primary_transport_id = fields.Many2one(
        "conversation.transport",
        string="Primary Transport",
        help="Soft default transport for this conversation's outbound "
        "replies; individual messages may carry their own transport_id.",
    )
    link_ids = fields.One2many(
        "mail.conversation.link",
        "conversation_id",
        string="Linked Records",
    )
    participant_ids = fields.One2many(
        "mail.conversation.participant",
        "conversation_id",
        string="Participants",
    )
    member_ids = fields.One2many(
        "mail.conversation.member",
        "conversation_id",
        string="Members",
    )

    # ------------------------------------------------------------
    # Mail Alias Mixin
    # ------------------------------------------------------------

    def _alias_get_creation_values(self):
        values = super()._alias_get_creation_values()
        values["alias_model_id"] = self.env["ir.model"]._get_id("mail.conversation")
        if self.id:
            values["alias_defaults"] = defaults = ast.literal_eval(
                self.alias_defaults or "{}"
            )
            if self.team_id:
                defaults["team_id"] = self.team_id.id
        return values

    # ------------------------------------------------------------
    # Gateway hygiene -- inbound mail creating/threading into a
    # conversation must populate participants, never followers (see
    # mail.conversation.participant docstring / project invariant).
    # ------------------------------------------------------------

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        conversation = super().message_new(msg_dict, custom_values)
        conversation._sync_participants_from_msg_dict(msg_dict)
        return conversation

    def _sync_participants_from_msg_dict(self, msg_dict):
        """Build ``mail.conversation.participant`` rows from a gateway
        ``msg_dict`` (as produced by ``mail.thread.message_parse``/
        ``message_route``: comma-joined ``to``/``cc`` strings, a resolved
        ``author_id``). Used by ``message_new`` (real inbound via the
        alias) and by ``_route_via_alias`` (a captured stub routed through
        the gateway).
        """
        self.ensure_one()
        author_id = msg_dict.get("author_id")
        author_partner = (
            self.env["res.partner"].browse(author_id) if author_id else False
        )
        self._sync_participants(
            from_email=msg_dict.get("email_from") or msg_dict.get("from"),
            from_partner=author_partner,
            to_emails=tools.email_split(msg_dict.get("to") or ""),
            cc_emails=tools.email_split(msg_dict.get("cc") or ""),
        )

    def _sync_participants_from_stub(self, stub):
        """Build ``mail.conversation.participant`` rows from a normalized
        transport stub (as produced by ``conversation.transport._normalize``:
        ``email_from``/``author``, ``to``/``cc`` as lists). Used when a
        human quiet-captures an inbox item (``_capture_stub``).
        """
        self.ensure_one()
        author_id = stub.get("author_id")
        author_partner = (
            self.env["res.partner"].browse(author_id) if author_id else False
        )
        self._sync_participants(
            from_email=stub.get("email_from") or stub.get("author"),
            from_partner=author_partner,
            to_emails=stub.get("to") or [],
            cc_emails=stub.get("cc") or [],
        )

    def _sync_participants(
        self, from_email=None, from_partner=None, to_emails=None, cc_emails=None
    ):
        """Correct-correspondent mapping (AC8): the From address/partner
        becomes the conversation's ``requester`` participant -- the actual
        correspondent/customer, never the acting/capturing user. To/Cc
        addresses are added as ``to``/``cc`` participants. Dedup and
        partner resolution both key off ``email_normalized``; never calls
        ``message_subscribe``.
        """
        self.ensure_one()
        Participant = self.env["mail.conversation.participant"]
        if from_email:
            partner = from_partner or self._find_partner_by_email(from_email)
            Participant._get_or_create(
                self, from_email, partner=partner, role="requester"
            )
        for email in to_emails or []:
            Participant._get_or_create(
                self, email, partner=self._find_partner_by_email(email), role="to"
            )
        for email in cc_emails or []:
            Participant._get_or_create(
                self, email, partner=self._find_partner_by_email(email), role="cc"
            )

    def _find_partner_by_email(self, email):
        normalized = tools.email_normalize(email)
        if not normalized:
            return self.env["res.partner"]
        return (
            self.env["res.partner"]
            .sudo()
            .search([("email_normalized", "=", normalized)], limit=1)
        )

    # ------------------------------------------------------------
    # Capture / GTD funnel (epic 03, task #3965). Quiet capture posts an
    # internal note (transport_id falsy) so no external party is
    # re-notified -- see the project's notification-safety invariant; the
    # generalized _notify_get_recipients override lands in epic 05 and is
    # deliberately NOT relied on here.
    # ------------------------------------------------------------

    @api.model
    def _capture_stub(self, transport, stub, mode="new", target=None):
        """Quiet-capture an inbox stub (a normalized envelope, as returned
        by ``transport._normalize``/``fetch_envelope``) into the hub,
        without persisting anything on the remote mailbox and without
        re-notifying the original recipients.

        :param transport: the ``conversation.transport`` the stub came
            from.
        :param dict stub: canonical envelope -- ``subject``, ``body``,
            ``email_from``/``author``, ``to``, ``cc``, ``external_id``,
            optionally ``author_id`` (a resolved ``res.partner`` id).
        :param str mode: ``'new'`` (default) creates a new conversation;
            ``'existing'`` threads into ``target`` (a ``mail.conversation``);
            ``'link'`` creates a new conversation and links it to ``target``
            (any business record) via ``mail.conversation.link``.
        :param target: see ``mode``.
        :return: the ``mail.conversation`` the stub was captured into.
        """
        if mode == "existing":
            if not target or target._name != "mail.conversation":
                raise UserError(
                    _("Pick an existing conversation to add this item to.")
                )
            conversation = target
        else:
            # mail_create_nolog: a captured conversation's timeline should
            # show the captured item, not Odoo's generic "Conversation
            # created" boilerplate on top of it. mail_create_nosubscribe:
            # quiet capture must not incidentally auto-follow the filing
            # user either -- conversation assignment is a deliberate
            # action (action_reassign), not a side effect of who happened
            # to triage the inbox.
            conversation = self.with_context(
                mail_create_nolog=True, mail_create_nosubscribe=True
            ).create(
                {
                    "name": stub.get("subject") or _("(no subject)"),
                    "primary_transport_id": transport.id,
                }
            )
            if mode == "link":
                if not target:
                    raise UserError(
                        _("Pick a record to link this captured item to.")
                    )
                self.env["mail.conversation.link"].create(
                    {
                        "conversation_id": conversation.id,
                        "res_model": target._name,
                        "res_id": target.id,
                        "reason": "manual",
                    }
                )

        conversation._sync_participants_from_stub(stub)

        post_kwargs = {
            # stub bodies come from transport._normalize(), already HTML
            # (or plaintext already escaped/converted via
            # odoo.tools.plaintext2html) -- wrap in Markup so
            # message_post doesn't re-escape it a second time.
            "body": Markup(stub.get("body") or ""),
            "subject": stub.get("subject"),
            "subtype_xmlid": "mail.mt_note",
        }
        author_id = stub.get("author_id")
        if author_id:
            post_kwargs["author_id"] = author_id
        else:
            # No resolved partner: pass email_from so _message_compute_author
            # can look one up (or fall back to a bare-email author) instead
            # of raising -- passing author_id=False without an email_from
            # would otherwise be treated as "no author at all".
            post_kwargs["email_from"] = stub.get("email_from") or stub.get(
                "author"
            )
        message = conversation.message_post(**post_kwargs)
        # transport_id stays FALSY here by design: it is the model-contract
        # marker for "internal note" (mail.message docstring), and the
        # notification-safety invariant this quiet capture leans on is the
        # subtype (mt_note) + a falsy transport_id -- the generalized
        # _notify_get_recipients override that would make a non-falsy
        # transport_id safe too lands in epic 05, not here (see Risks in
        # the task design). external_id still records provenance/dedup;
        # conversation.primary_transport_id records which transport this
        # came from at the conversation level.
        # message_id records the captured email's real RFC822 Message-Id,
        # overwriting the one message_post just minted for an Odoo-native
        # message: it is what a correspondent's client quotes back in
        # In-Reply-To/References, so it is the only id an outbound reply
        # can thread against (see _imap_reply_headers). external_id keeps
        # holding the transport's own native id -- an IMAP UID, which is
        # meaningless outside that one mailbox -- for provenance and
        # capture-idempotency lookups.
        message.write(
            {
                "external_id": stub.get("external_id"),
                "message_id": stub.get("message_id") or message.message_id,
            }
        )
        return conversation

    @api.model
    def _find_captured(self, transport, external_id):
        """Idempotent-capture lookup: has this transport's ``external_id``
        already been filed into a conversation? Captured notes carry a
        falsy ``transport_id`` by design (AC7/AC8's notify-safety marker),
        so provenance is matched on ``external_id`` + the conversation's
        ``primary_transport_id`` instead of ``mail.message.transport_id``.
        Returns an empty ``mail.conversation`` recordset if not found.
        """
        message = self.env["mail.message"].search(
            [("model", "=", self._name), ("external_id", "=", external_id)],
            limit=1,
        )
        if message and message.res_id:
            conversation = self.browse(message.res_id)
            if conversation.primary_transport_id == transport:
                return conversation
        return self.browse()

    @api.model
    def _capture_or_find(self, transport, external_id):
        """Fetch+normalize+capture ``external_id`` as a new conversation,
        unless it was already captured earlier -- then return that same
        conversation instead of filing a duplicate. Used by the inbox GTD
        actions (reply/forward/reassign/dismiss) so acting twice on the
        same inbox item never creates two conversations.
        """
        existing = self._find_captured(transport, external_id)
        if existing:
            return existing
        raw = transport._fetch(external_id)
        stub = transport._normalize(raw)
        return self._capture_stub(transport, stub, mode="new")

    def _all_participant_emails(self, roles=("to", "cc", "requester")):
        """Deduplicated participant emails for the given roles, in
        participant order. Used to build an explicit reply-all recipient
        list (roles including ``cc``) as distinct from a plain reply
        (``transport._send``'s own default recipients, to/requester only,
        when no explicit ``recipients`` are passed to ``action_reply``).
        """
        self.ensure_one()
        participants = self.participant_ids.filtered(
            lambda p: p.role in roles and p.email_normalized
        )
        return list(dict.fromkeys(participants.mapped("email_normalized")))

    @api.model
    def _route_via_alias(self, raw_rfc822, model="mail.conversation"):
        """Feed a raw RFC822 message (captured from a browsable transport)
        into the ordinary mail gateway (``mail.thread.message_process``) so
        alias-based routing and In-Reply-To/References threading fire
        exactly as they would for a real inbound -- the 'route through an
        alias' GTD action.
        """
        thread_id = self.env["mail.thread"].message_process(model, raw_rfc822)
        return self.browse(thread_id) if thread_id else self.browse()

    # ------------------------------------------------------------
    # GTD actions -- reply / forward / reassign / archive. Outbound
    # delivery always goes through the transport's explicit _send, never
    # Odoo's notification pipeline (notification-safety invariant).
    # ------------------------------------------------------------

    def _get_sendable_transport(self, transport=None):
        self.ensure_one()
        transport = transport or self.primary_transport_id
        if not transport or not transport.sendable:
            raise UserError(
                _("This conversation has no sendable transport configured.")
            )
        return transport

    def action_reply(self, body, recipients=None, transport=None, subtype_xmlid="mail.mt_comment"):
        """Reply (or reply-all, when ``recipients`` includes the Cc
        participants) on this conversation's primary transport (or the
        explicit ``transport``). ``recipients``: optional explicit list of
        email strings; defaults to the transport's own recipient
        computation from the conversation's participants.
        """
        self.ensure_one()
        transport = self._get_sendable_transport(transport)
        # body comes from the composer (rich-text HTML), not a plain
        # string to be escaped -- wrap in Markup to avoid a double-escape.
        message = self.message_post(
            body=Markup(body or ""), subtype_xmlid=subtype_xmlid
        )
        message.write({"transport_id": transport.id})
        external_id = transport._send(self, message, recipients=recipients)
        if external_id:
            message.external_id = external_id
        return message

    def action_forward(self, body, to_emails, transport=None):
        """Forward-like-email: send to any address (partner or not),
        without requiring the recipient to already be a participant. This
        is a lightweight "compose + transport._send" action distinct from
        the conversation-level Forward shipped in epic 08
        (``mail_manual_routing_ux``) -- see task design notes.
        """
        self.ensure_one()
        transport = self._get_sendable_transport(transport)
        if isinstance(to_emails, str):
            to_emails = [to_emails]
        # An empty body is legitimate on a forward: the original alone
        # is the message.
        message = self.message_post(
            body=Markup(body or ""), subtype_xmlid="mail.mt_note"
        )
        message.write({"transport_id": transport.id})
        external_id = transport._send(self, message, recipients=to_emails)
        if external_id:
            message.external_id = external_id
        return message

    def _record_outbound(
        self,
        transport,
        subject,
        body,
        message_id,
        to_emails=None,
        cc_emails=None,
        attachment_ids=None,
    ):
        """Record a message that has ALREADY been sent over ``transport``
        (by ``_send_raw``) onto this conversation, without sending it a
        second time.

        The composer sends first and files second, because filing is
        optional: only the filed path reaches this, and by then the mail
        is on the wire. ``message_id`` is the id that actually went out,
        so a reply quoting it correlates back here.

        ``attachment_ids`` are the files that went out with it, so the
        filed conversation reads as what was actually sent rather than as
        a body whose "see attached" refers to nothing. They are re-homed
        onto this conversation first: ``message_post`` only re-points
        attachments that came from ``mail.compose.message`` or
        ``mail.scheduled.message``, so anything composed elsewhere would
        otherwise stay pointing at a record that is about to cease to
        exist.

        Bcc recipients are deliberately NOT recorded. Filing an exchange
        into a shared hub must not disclose who was blind-copied -- that
        is the one thing a Bcc promises.
        """
        self.ensure_one()
        attachments = self.env["ir.attachment"].browse(attachment_ids or [])
        if attachments:
            attachments.sudo().write({"res_model": self._name, "res_id": self.id})
        message = self.message_post(
            body=Markup(body or ""),
            subject=subject,
            subtype_xmlid="mail.mt_comment",
            attachment_ids=attachments.ids,
        )
        message.write(
            {
                "transport_id": transport.id,
                "message_id": message_id,
                "external_id": (message_id or "").strip("<>") or False,
            }
        )
        self._sync_participants(
            to_emails=list(to_emails or []), cc_emails=list(cc_emails or [])
        )
        return message

    def action_reassign(self, user=None, team=None):
        """Hand this conversation to a colleague and/or a team."""
        self.ensure_one()
        vals = {}
        if user is not None:
            vals["user_id"] = user.id if user else False
        if team is not None:
            vals["team_id"] = team.id if team else False
        if vals:
            self.write(vals)
        return True

    def action_archive(self):
        """Mark the conversation done -- the closest single-item
        equivalent to "archive" on the existing ``state`` field. The
        durable per-user 'handled' checkmark and bulk-archive UX are
        epic 04's (#3966) job.
        """
        self.write({"state": "done"})
        return True
