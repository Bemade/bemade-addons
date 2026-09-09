# Acceptance criteria (task #3965, AC1):
#   AC-1: conversation.transport ships capability flags defaulting False and
#         abstract hooks that raise NotImplementedError on the base -- the
#         interface only, no hardcoded provider. One light assertion per the
#         design's test plan, not a suite (providers get the real coverage).
#   AC-5: browse_page/fetch_envelope are the RPC entry points the OWL inbox
#         client calls directly by transport id (conversation_inbox.js).
#         Their gating-on-browsable was covered for browse_page but not
#         fetch_envelope, and neither had a happy-path test showing they
#         actually delegate to the hooks -- covered here at the base-stub
#         level (with the hooks mocked out, since the base itself only
#         implements the dispatch/gating, not a real provider).

from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import TransactionCase


class TestConversationTransportInterface(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Bare Transport"}
        )

    def test_capability_flags_default_false(self):
        for flag in (
            "browsable",
            "searchable",
            "pushable",
            "sendable",
            "artifact_only",
        ):
            self.assertFalse(
                self.transport[flag], f"{flag} should default to False"
            )

    def test_abstract_hooks_raise_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.transport._browse()
        with self.assertRaises(NotImplementedError):
            self.transport._search_remote({})
        with self.assertRaises(NotImplementedError):
            self.transport._fetch("ext-1")
        with self.assertRaises(NotImplementedError):
            self.transport._normalize({})
        with self.assertRaises(NotImplementedError):
            self.transport._match_inbound({})
        with self.assertRaises(NotImplementedError):
            self.transport._send(self.env["mail.conversation"], self.env["mail.message"])
        with self.assertRaises(NotImplementedError):
            self.transport._subscribe_push()

    def test_browse_page_gated_on_browsable(self):
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            self.transport.browse_page(self.transport.id)

    def test_browse_page_delegates_to_browse_when_browsable(self):
        browsable = self.env["conversation.transport"].create(
            {"name": "Browsable Transport", "browsable": True}
        )
        transport_model = type(browsable)
        with patch.object(
            transport_model, "_browse", return_value=[{"external_id": "1"}], autospec=True
        ) as mocked_browse:
            result = browsable.browse_page(browsable.id, query="foo", page=2)
        mocked_browse.assert_called_once_with(browsable, query="foo", page=2)
        self.assertEqual(result, [{"external_id": "1"}])

    def test_fetch_envelope_gated_on_browsable(self):
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            self.transport.fetch_envelope(self.transport.id, "ext-1")

    def test_fetch_envelope_delegates_to_fetch_and_normalize(self):
        browsable = self.env["conversation.transport"].create(
            {"name": "Browsable Transport 2", "browsable": True}
        )
        transport_model = type(browsable)
        with patch.object(
            transport_model, "_fetch", return_value={"raw": True}, autospec=True
        ) as mocked_fetch, patch.object(
            transport_model,
            "_normalize",
            return_value={"subject": "Hi", "external_id": "ext-9"},
            autospec=True,
        ) as mocked_normalize:
            stub = browsable.fetch_envelope(browsable.id, "ext-9")
        mocked_fetch.assert_called_once_with(browsable, "ext-9")
        mocked_normalize.assert_called_once_with(browsable, {"raw": True})
        self.assertEqual(stub, {"subject": "Hi", "external_id": "ext-9"})


class TestConversationTransportVisibility(TransactionCase):
    # Acceptance criteria (task #3965, AC10 -- soft-launch / model-reuse
    # compliance): 02-design.md's "Data model changes" adds the
    # `conversation_transport_rule_own_or_shared` ir.rule so a
    # base.group_user only sees/edits transports they own (user_id = uid)
    # plus shared/team ones (user_id falsy). This is real row-level access
    # control guarding private mail-account credentials (IMAP passwords /
    # OAuth refresh tokens) -- a typo'd domain_force would silently leak
    # one user's mail account to every other internal user, or silently
    # hide a shared account from everyone. Untested until now.
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_a = cls.env["res.users"].create(
            {
                "name": "Transport Owner A",
                "login": "transport-owner-a@example.com",
                "groups_id": [Command.link(cls.env.ref("base.group_user").id)],
            }
        )
        cls.user_b = cls.env["res.users"].create(
            {
                "name": "Transport Owner B",
                "login": "transport-owner-b@example.com",
                "groups_id": [Command.link(cls.env.ref("base.group_user").id)],
            }
        )
        Transport = cls.env["conversation.transport"].sudo()
        cls.private_a = Transport.create(
            {"name": "A's Private Inbox", "user_id": cls.user_a.id}
        )
        cls.shared = Transport.create({"name": "Shared Team Inbox"})

    def test_owner_sees_own_and_shared_transports(self):
        Transport = self.env["conversation.transport"].with_user(self.user_a)
        visible = Transport.search(
            [("id", "in", [self.private_a.id, self.shared.id])]
        )
        self.assertEqual(set(visible.ids), {self.private_a.id, self.shared.id})

    def test_other_user_sees_only_shared_transport(self):
        Transport = self.env["conversation.transport"].with_user(self.user_b)
        visible = Transport.search(
            [("id", "in", [self.private_a.id, self.shared.id])]
        )
        self.assertEqual(visible.ids, [self.shared.id])

    def test_other_user_cannot_read_private_transport_by_id(self):
        with self.assertRaises(AccessError):
            self.private_a.with_user(self.user_b).read(["name"])
