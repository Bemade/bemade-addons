from odoo import fields, models


class MailMessage(models.Model):
    """Extend mail.message with transport-level metadata so an individual
    message can be told apart from an internal note (``transport_id`` is
    falsy for internal notes, e.g. ``mt_note`` messages) and correlated
    back to the native id of the message on the originating transport
    (Gmail/Graph message id, WhatsApp ``wamid``, IMAP UID, ...).
    """

    _inherit = "mail.message"

    transport_id = fields.Many2one(
        "conversation.transport",
        string="Transport",
        index=True,
        help="The channel this message was sent/received over. Falsy for "
        "internal notes.",
    )
    external_id = fields.Char(
        index=True,
        help="Native id of this message on its transport (e.g. Gmail/Graph "
        "message id, WhatsApp wamid, IMAP UID), used for correlation.",
    )
