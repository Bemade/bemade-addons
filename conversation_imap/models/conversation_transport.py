from odoo import fields, models


class ConversationTransport(models.Model):
    """Generic IMAP/SMTP provider: a manually-configured account
    authenticating with ``login``/``password`` against a host/port the user
    supplies.

    The browse/fetch/normalize/match/send implementation itself lives in
    ``conversation_email_base`` and is shared with every other
    email-speaking provider -- this module contributes only the connection
    *configuration* (task #3965): the ``provider`` code, the endpoint
    fields, and the password. It deliberately does **not** override
    ``_imap_oauth_string``: generic IMAP has no OAuth mechanism of its own,
    so the engine's ``None`` default (plain password login) is correct here.
    """

    _inherit = "conversation.transport"

    provider = fields.Selection(
        selection_add=[("imap", "IMAP / Generic Email")],
        ondelete={"imap": "cascade"},
        default="imap",
    )

    imap_host = fields.Char(string="IMAP Server")
    imap_port = fields.Integer(string="IMAP Port", default=993)
    imap_ssl = fields.Boolean(string="IMAP over SSL", default=True)
    smtp_host = fields.Char(string="SMTP Server")
    smtp_port = fields.Integer(string="SMTP Port", default=587)
    smtp_ssl = fields.Boolean(
        string="SMTP over STARTTLS",
        default=True,
        help="Use STARTTLS on the SMTP connection (the common case on port "
        "587). Leave off only for a plain/legacy relay.",
    )
    password = fields.Char(
        help="IMAP/SMTP account password. Generic IMAP has no universal "
        "OAuth mechanism, so this stays a plain stored secret -- scoped "
        "like the rest of conversation.transport by the conversation_base "
        "ir.rule (own + shared transports only). Left blank on an "
        "OAuth-connected account (conversation_gmail, ...): those "
        "authenticate with a token instead, never a stored password.",
    )

    def _email_providers(self):
        return super()._email_providers() + ["imap"]

    def _email_connection_params(self):
        # Provider-guarded, not load-order-dependent: another provider
        # module's transports must keep their own endpoints even though
        # this module also extends conversation.transport.
        if self.provider != "imap":
            return super()._email_connection_params()
        return {
            "imap_host": self.imap_host,
            "imap_port": self.imap_port or 993,
            "imap_ssl": self.imap_ssl,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port or 587,
            "smtp_starttls": self.smtp_ssl,
            "password": self.password,
        }
