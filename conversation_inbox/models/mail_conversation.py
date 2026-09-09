from odoo import _, api, models
from odoo.exceptions import UserError


class MailConversation(models.Model):
    """Inbox-viewer-specific GTD action entry points (task #3965). These
    take plain ids (not recordsets) so the OWL inbox client can call them
    directly by RPC without a prior ``browse``/``read``.
    """

    _inherit = "mail.conversation"

    @api.model
    def action_dismiss(self, transport_id, external_id):
        """GTD delete/archive on an inbox item. Ingest-on-action means
        nothing is persisted until a human files an item (AC5) -- so if
        this ``external_id`` was never captured, there is nothing to
        delete server-side: dismissing it is a pure client-side action
        (the item simply isn't filed). If it *was* already captured (e.g.
        the user replied to it earlier, then comes back to dismiss it),
        archive that conversation instead of silently doing nothing.

        :return: True if an existing conversation was archived, False if
            this was a no-op (item was never filed).
        """
        transport = self.env["conversation.transport"].browse(transport_id)
        conversation = self._find_captured(transport, external_id)
        if conversation:
            conversation.action_archive()
        return bool(conversation)

    @api.model
    def action_route_via_alias(self, transport_id, external_id, model="mail.conversation"):
        """GTD 'route through an alias' action: feed the raw envelope for
        this inbox item into the ordinary mail gateway
        (``_route_via_alias``) so alias routing/threading/automation fire
        exactly as for a real inbound. Only meaningful for transports
        whose ``_fetch`` raw envelope carries the transport-native RFC822
        bytes (``raw['rfc822']`` -- true for the IMAP-family providers,
        conversation_imap/conversation_gmail); other transport shapes
        raise a clear error rather than silently doing nothing.

        :return: the id of the conversation the alias routed the message
            into (0/False if none matched/was created).
        """
        transport = self.env["conversation.transport"].browse(transport_id)
        raw = transport._fetch(external_id)
        rfc822 = raw.get("rfc822") if isinstance(raw, dict) else None
        if not rfc822:
            raise UserError(
                _(
                    "%(transport)s doesn't expose a raw message this "
                    "action can route through an alias.",
                    transport=transport.display_name,
                )
            )
        conversation = self._route_via_alias(rfc822, model=model)
        return conversation.id if conversation else False
