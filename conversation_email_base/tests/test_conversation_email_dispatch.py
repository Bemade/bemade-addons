# Acceptance criteria (task #3965, conversation_email_base):
#   The engine claims every conversation.transport hook (_browse, _fetch,
#   _normalize, _match_inbound, _send, _search_remote) for the whole model,
#   because that is the only way Odoo lets a module extend one. It must
#   therefore hand a NON-email transport straight back to
#   conversation_base's abstract hooks instead of trying to open an IMAP
#   connection for it -- otherwise installing this module would break every
#   future non-email provider (SMS, WhatsApp, ...) the moment one exists.
#
#   The engine's actual IMAP/SMTP behaviour is not mocked up here: it is
#   exercised end to end through the real providers that supply its
#   connection layer (conversation_imap's and conversation_gmail's test
#   suites), which is where a regression would actually bite.

from odoo.tests import TransactionCase


class TestConversationEmailDispatch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # provider is deliberately blanked (not merely omitted -- an
        # installed provider module may supply a default): this stands in
        # for a transport belonging to some other, non-email provider.
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Not An Email Transport",
                "provider": False,
                "login": "somewhere@example.com",
            }
        )

    def test_non_email_transport_falls_through_to_abstract_hooks(self):
        self.assertFalse(self.transport._is_email_transport())
        for call in (
            lambda: self.transport._browse(),
            lambda: self.transport._search_remote({}),
            lambda: self.transport._fetch("1"),
            lambda: self.transport._normalize({}),
            lambda: self.transport._match_inbound({}),
            lambda: self.transport._send(
                self.env["mail.conversation"], self.env["mail.message"]
            ),
            lambda: self.transport._subscribe_push(),
        ):
            with self.assertRaises(NotImplementedError):
                call()
