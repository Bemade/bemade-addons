import base64
import email
import email.policy
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.addons.conversation_base.tools import mime
from odoo.exceptions import UserError
from odoo.tools import format_datetime, html_sanitize

_logger = logging.getLogger(__name__)


class ConversationInboxReplyWizard(models.TransientModel):
    """GTD reply / reply-all / forward composer (task #3965, AC6e/f).

    Two things make this deliberately NOT an inherit of
    ``mail.compose.message``:

    * That model exists to persist -- it creates ``mail.mail`` and
      ``mail.message`` records and sends through ``ir.mail_server``. The
      default path here must do none of those things: a personal mailbox's
      traffic does not belong in the shared hub unless the user says so
      (``file_in_odoo``, off by default).
    * Sending always goes through the triaged account's OWN transport, so
      a reply leaves from the address the original arrived at.

    So the widgets are reused, not the model.

    Recipients are free text on purpose: a correspondent is very often not
    a partner, and a forward explicitly accepts any address. Partner
    matching happens after the send, and only on the filed path.
    """

    _name = "conversation.inbox.reply.wizard"
    _description = "Reply/Forward Inbox Item"

    transport_id = fields.Many2one(
        "conversation.transport", required=True, readonly=True
    )
    external_id = fields.Char(required=True, readonly=True)
    action_type = fields.Selection(
        [("reply", "Reply"), ("reply_all", "Reply All"), ("forward", "Forward")],
        default="reply",
        required=True,
    )
    subject = fields.Char()
    to_emails = fields.Char(
        string="To",
        help="Comma-separated recipient address(es) -- any address, "
        "whether or not it is already a participant.",
    )
    cc_emails = fields.Char(string="Cc", help="Comma-separated.")
    bcc_emails = fields.Char(
        string="Bcc",
        help="Comma-separated. Sent in the SMTP envelope only -- never a "
        "header, and never recorded in Odoo when filing.",
    )
    body = fields.Html(
        help="Prefilled with your signature and the quoted original so "
        "you can trim either. Optional on a forward: passing an email "
        "along with no added comment is ordinary use.",
    )
    in_reply_to = fields.Char(readonly=True)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Attachments",
        help="Files you add here. On a forward the original's own "
        "attachments are carried over separately -- see Forwarded Files.",
    )
    forwarded_filenames = fields.Char(
        string="Forwarded Files",
        readonly=True,
        help="The original's attachments, which are re-attached to the "
        "forward. They are fetched from the mailbox at send time rather "
        "than copied into Odoo, so forwarding stores nothing here.",
    )
    file_in_odoo = fields.Boolean(
        string="File in Odoo",
        help="Record this exchange as a conversation in the hub. Off by "
        "default: triage from a personal mailbox should not persist "
        "message bodies into shared storage unless you choose to.",
    )
    filing_mode = fields.Selection(
        [("new", "New conversation"), ("existing", "Add to existing")],
        default="new",
    )
    conversation_id = fields.Many2one(
        "mail.conversation",
        string="Conversation",
        help="Most recent first. Relevance ranking is task #4128.",
    )

    # ------------------------------------------------------------
    # Defaults -- everything the composer prefills comes from the
    # original envelope, fetched once here rather than passed through the
    # client (which only knows the item's id).
    # ------------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        transport = self.env["conversation.transport"].browse(
            values.get("transport_id")
        )
        external_id = values.get("external_id")
        if not transport or not external_id:
            return values
        values.setdefault("file_in_odoo", transport.default_file_in_odoo)
        try:
            stub = transport._normalize(transport._fetch(external_id))
        except Exception:  # noqa: BLE001 - see below
            # An unreachable mailbox (network, expired token, a transport
            # that cannot fetch at all) must still leave the user with a
            # usable composer: prefilling is a convenience, and failing
            # here would replace the dialog with a traceback.
            _logger.warning(
                "Could not prefill the composer from %s on %s",
                external_id,
                transport.display_name,
                exc_info=True,
            )
            return values
        action_type = values.get("action_type") or "reply"
        values.update(self._compose_defaults(transport, stub, action_type))
        return values

    def _compose_defaults(self, transport, stub, action_type):
        """Recipients, subject and prefilled body for one action type."""
        subject = stub.get("subject") or ""
        values = {
            "in_reply_to": stub.get("message_id") or False,
            "subject": self._prefixed_subject(subject, action_type),
            "body": self._quoted_body(stub, action_type),
        }
        if action_type == "forward":
            # A forward's recipient is never derivable -- that is the
            # whole point of forwarding -- so To stays empty for the user.
            values["forwarded_filenames"] = ", ".join(
                attachment.get("filename") or _("attachment")
                for attachment in stub.get("attachments") or []
            )
            return values
        values["to_emails"] = stub.get("email_from") or ""
        if action_type == "reply_all":
            # Everyone else who was on it, minus this account itself --
            # replying all to yourself is noise, and on a shared mailbox
            # it is a loop.
            own = (transport.login or "").lower()
            others = [
                address
                for address in (stub.get("to") or []) + (stub.get("cc") or [])
                if address and address.lower() != own
            ]
            values["cc_emails"] = ", ".join(dict.fromkeys(others))
        return values

    def _prefixed_subject(self, subject, action_type):
        prefix = _("Fwd:") if action_type == "forward" else _("Re:")
        if subject.lower().startswith(prefix.lower()):
            return subject
        return "%s %s" % (prefix, subject) if subject else prefix

    def _quoted_body(self, stub, action_type):
        """Signature + the quoted original, prefilled into the editable
        body rather than appended at send time: one mechanism covers
        reply-quoting, forward-quoting and the signature, and the user can
        trim any of it. Modelled on ``mail_quoted_reply``'s block, which
        Durpro already runs, so a quoted message looks the same wherever
        it was composed.

        The signature is the ACTING USER's (``env.user.signature``), which
        is what Odoo does everywhere else. That is right for a personal
        mailbox and an open question for a shared one: a message leaving
        support@ signed by whoever happened to triage it may be exactly
        what you want, or may be a leak of who is behind the desk. Left as
        the user's signature deliberately, pending a decision -- see the
        README's open-design-question section.
        """
        header = _("Forwarded message") if action_type == "forward" else None
        rows = [
            (_("From"), stub.get("email_from") or ""),
            (_("Date"), self._format_stub_date(stub.get("date"))),
            (_("Subject"), stub.get("subject") or ""),
        ]
        if stub.get("to"):
            rows.append((_("To"), ", ".join(stub["to"])))
        quoted_rows = Markup("").join(
            Markup("<b>%s:</b> %s<br/>") % (label, value) for label, value in rows
        )
        return Markup(
            '<p><br/></p>%(signature)s<p><br/></p>'
            '<blockquote style="padding-right:0px; padding-left:5px; '
            'border-left-color:#000; margin-left:5px; margin-right:0px; '
            'border-left-width:2px; border-left-style:solid">'
            "%(header)s%(rows)s<br/>%(body)s</blockquote>"
        ) % {
            "signature": Markup(self.env.user.signature or ""),
            "header": Markup("<p><b>%s</b></p>") % header if header else Markup(""),
            "rows": quoted_rows,
            "body": Markup(html_sanitize(stub.get("body") or "")),
        }

    def _format_stub_date(self, value):
        if not value:
            return ""
        try:
            return format_datetime(self.env, value)
        except (TypeError, ValueError):
            return str(value)

    # ------------------------------------------------------------
    # Send
    # ------------------------------------------------------------

    def _split_addresses(self, value):
        return [part.strip() for part in (value or "").split(",") if part.strip()]

    def _forwarded_attachments(self):
        """The original's own attachments, decoded straight from the
        source mailbox at send time. Deliberately NOT copied into
        ``ir.attachment`` first: the unfiled path must leave nothing in
        Odoo, and a transient attachment row is still stored content."""
        self.ensure_one()
        if self.action_type != "forward":
            return []
        raw = self.transport_id._fetch(self.external_id)
        parsed = email.message_from_bytes(
            raw["rfc822"], policy=email.policy.default
        )
        return mime.extract_attachment_payloads(parsed)

    def _own_attachments(self):
        """Files the user added, as the plain dicts _send_raw takes.
        Converted here rather than through a transport helper: this wizard
        depends only on conversation_base's interface, not on any one
        provider's engine."""
        self.ensure_one()
        return [
            {
                "filename": attachment.name,
                "content": base64.b64decode(attachment.datas or b""),
                "mimetype": attachment.mimetype,
            }
            for attachment in self.attachment_ids
        ]

    def action_send(self):
        self.ensure_one()
        to_emails = self._split_addresses(self.to_emails)
        cc_emails = self._split_addresses(self.cc_emails)
        bcc_emails = self._split_addresses(self.bcc_emails)
        if not (to_emails or cc_emails or bcc_emails):
            raise UserError(_("Enter at least one recipient."))

        attachments = self._forwarded_attachments() + self._own_attachments()
        message_id = self.transport_id._send_raw(
            subject=self.subject or "",
            body=self.body or "",
            to_emails=to_emails,
            cc=cc_emails,
            bcc=bcc_emails,
            in_reply_to=self.in_reply_to or None,
            attachments=attachments,
        )
        if not self.file_in_odoo:
            # Nothing is recorded in Odoo at all -- the whole point of the
            # default path, and it has to be true of the database and not
            # merely of mail.message. This wizard row holds the draft, the
            # recipients and the Bcc list, and its attachments are
            # ordinary ir.attachment records: without this the row lives
            # until the DAILY autovacuum cron and the attachments live
            # forever, orphaned but never collected (the filestore GC only
            # removes files that no attachment row references).
            self._discard(unlink_attachments=True)
            return {"type": "ir.actions.act_window_close"}
        conversation = self._file_exchange()
        conversation._record_outbound(
            self.transport_id,
            self.subject or "",
            self.body or "",
            message_id,
            to_emails=to_emails,
            cc_emails=cc_emails,
            attachment_ids=self.attachment_ids.ids,
        )
        action = {
            "type": "ir.actions.act_window",
            "res_model": "mail.conversation",
            "res_id": conversation.id,
            "views": [[False, "form"]],
            "target": "current",
        }
        # The attachments now belong to the conversation, so only the row
        # itself goes -- it still carries the Bcc list that _record_outbound
        # deliberately kept off the conversation.
        self._discard()
        return action

    def _discard(self, unlink_attachments=False):
        """Drop the wizard row once the send is done, and optionally the
        files with it. Best-effort: the mail is already on the wire by the
        time this runs, so failing to tidy up must never surface as a send
        failure."""
        self.ensure_one()
        attachments = self.attachment_ids if unlink_attachments else None
        try:
            if attachments:
                attachments.sudo().unlink()
            self.sudo().unlink()
        except Exception:  # noqa: BLE001 - tidying, never the user's problem
            _logger.warning(
                "Could not discard composer %s after sending", self.id, exc_info=True
            )

    def _file_exchange(self):
        """File the ORIGINAL inbox item, so the conversation reads as the
        exchange it is rather than only our half of it. Idempotent: acting
        twice on the same item never files a second conversation."""
        self.ensure_one()
        Conversation = self.env["mail.conversation"]
        if self.filing_mode == "existing":
            if not self.conversation_id:
                raise UserError(_("Pick the conversation to add this to."))
            stub = self.transport_id._normalize(
                self.transport_id._fetch(self.external_id)
            )
            return Conversation._capture_stub(
                self.transport_id, stub, mode="existing", target=self.conversation_id
            )
        return Conversation._capture_or_find(self.transport_id, self.external_id)
