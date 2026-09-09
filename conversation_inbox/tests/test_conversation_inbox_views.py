# Acceptance criteria (task #3965, test plan #9 -- view/asset smoke):
# Form builds for each wizard (guards missing view fields / broken
# invisible-domain expressions), and the client action + "My Mail
# Accounts" menu/action records this module ships resolve. Actually
# exercising the OWL runtime is out of scope for this headless Python
# test suite -- see the implementation notes' Deviations for what that
# would take (a hoot/tour browser test).

from odoo.tests import Form, TransactionCase


class TestConversationInboxViewSmoke(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "View Smoke Transport", "browsable": True}
        )

    def _defaults(self, external_id="ext-1"):
        # transport_id/external_id are readonly on all three wizards --
        # in real usage the OWL client seeds them via default_* context
        # (see conversation_inbox.js's _wizardContext), never direct form
        # edits, so the smoke test opens the Form the same way.
        return {
            "default_transport_id": self.transport.id,
            "default_external_id": external_id,
        }

    def test_capture_wizard_form_builds(self):
        Wizard = self.env["conversation.inbox.capture.wizard"].with_context(
            **self._defaults()
        )
        with Form(Wizard) as form:
            form.mode = "new"
        form.save()

    def test_reassign_wizard_form_builds(self):
        Wizard = self.env["conversation.inbox.reassign.wizard"].with_context(
            **self._defaults()
        )
        with Form(Wizard) as form:
            pass
        form.save()

    def test_reply_wizard_form_builds(self):
        Wizard = self.env["conversation.inbox.reply.wizard"].with_context(
            **self._defaults()
        )
        with Form(Wizard) as form:
            form.action_type = "reply"
            form.body = "<p>Hi</p>"
        form.save()

    def test_client_action_and_menus_resolve(self):
        self.assertTrue(
            self.env.ref("conversation_inbox.conversation_inbox_client_action")
        )
        self.assertTrue(self.env.ref("conversation_inbox.menu_conversation_inbox"))
        self.assertTrue(
            self.env.ref("conversation_inbox.conversation_transport_action_my")
        )
        self.assertTrue(
            self.env.ref("conversation_inbox.menu_conversation_transport_my")
        )
