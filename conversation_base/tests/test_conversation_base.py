from psycopg2 import IntegrityError

from odoo.tests import Form, TransactionCase
from odoo.tools.misc import mute_logger


class TestConversationBaseStub(TransactionCase):
    """Placeholder: kept so a minimal, dependency-free check always
    collects even if the behavioral suite below needs adjustment.
    """

    def test_model_registered(self):
        self.assertIn("mail.conversation", self.env)


class TestConversationBase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conversation = cls.env["mail.conversation"]
        cls.Link = cls.env["mail.conversation.link"]
        cls.Participant = cls.env["mail.conversation.participant"]
        cls.Member = cls.env["mail.conversation.member"]
        cls.partner_a = cls.env["res.partner"].create({"name": "Partner A"})
        cls.partner_b = cls.env["res.partner"].create({"name": "Partner B"})
        cls.partner_c = cls.env["res.partner"].create({"name": "Partner C"})
        cls.user = cls.env.ref("base.user_admin")

    def _make_conversation(self, name="Test Conversation"):
        return self.Conversation.create({"name": name})

    # ------------------------------------------------------------
    # AC5 - follower separation
    # ------------------------------------------------------------

    def test_participant_does_not_create_followers(self):
        conversation = self._make_conversation()
        self.Participant._get_or_create(
            conversation, "bare@example.com", partner=False
        )
        self.Participant._get_or_create(
            conversation, self.partner_a.email or "partnera@example.com",
            partner=self.partner_a,
        )
        self.assertFalse(conversation.message_follower_ids)
        followers = self.env["mail.followers"].search(
            [
                ("res_model", "=", "mail.conversation"),
                ("res_id", "=", conversation.id),
            ]
        )
        self.assertFalse(followers)

    # ------------------------------------------------------------
    # AC3 - bidirectional enumeration
    # ------------------------------------------------------------

    def test_bidirectional_link_enumeration(self):
        conversation = self._make_conversation("Conv 1")
        self.Link.create(
            {
                "conversation_id": conversation.id,
                "res_model": "res.partner",
                "res_id": self.partner_a.id,
            }
        )
        self.Link.create(
            {
                "conversation_id": conversation.id,
                "res_model": "res.partner",
                "res_id": self.partner_b.id,
            }
        )

        # record -> conversations (both directions of the link table,
        # per AC3: "record or partner ... via mail.conversation.link").
        # A res.partner is just a record here (res_model='res.partner'),
        # so partner->conversations enumeration IS record->conversations
        # enumeration with that model.
        found_for_a = self.Link._conversations_for_record(
            "res.partner", self.partner_a.id
        )
        self.assertEqual(found_for_a, conversation)
        found_for_b = self.Link._conversations_for_record(
            "res.partner", self.partner_b.id
        )
        self.assertEqual(found_for_b, conversation)

        # conversation -> records (the other direction).
        linked_models_ids = set(
            conversation.link_ids.mapped(lambda link: (link.res_model, link.res_id))
        )
        self.assertEqual(
            linked_models_ids,
            {
                ("res.partner", self.partner_a.id),
                ("res.partner", self.partner_b.id),
            },
        )

        # a second conversation on the same record is enumerated too.
        conversation2 = self._make_conversation("Conv 2")
        self.Link.create(
            {
                "conversation_id": conversation2.id,
                "res_model": "res.partner",
                "res_id": self.partner_a.id,
            }
        )
        found_for_a_both = self.Link._conversations_for_record(
            "res.partner", self.partner_a.id
        )
        self.assertEqual(found_for_a_both, conversation | conversation2)

    def test_participant_partner_enumeration_helper(self):
        # The implementation additionally exposes a participant-based
        # partner->conversations helper (beyond the AC3 link-table
        # requirement exercised above); exercise it too.
        conversation = self._make_conversation("Conv Participant")
        self.Participant._get_or_create(
            conversation, "someone@example.com", partner=self.partner_a
        )
        found = self.Participant._conversations_for_partner(self.partner_a)
        self.assertEqual(found, conversation)
        self.assertFalse(
            self.Participant._conversations_for_partner(self.partner_b)
        )

    # ------------------------------------------------------------
    # AC2 - link fan-out + uniqueness
    # ------------------------------------------------------------

    def test_link_fanout_and_uniqueness(self):
        conversation = self._make_conversation("Conv Fanout")
        partners = self.partner_a | self.partner_b | self.partner_c
        for partner in partners:
            self.Link.create(
                {
                    "conversation_id": conversation.id,
                    "res_model": "res.partner",
                    "res_id": partner.id,
                }
            )
        self.assertEqual(len(conversation.link_ids), 3)

        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.Link.create(
                    {
                        "conversation_id": conversation.id,
                        "res_model": "res.partner",
                        "res_id": self.partner_a.id,
                    }
                )

    # ------------------------------------------------------------
    # AC6 - member independence
    # ------------------------------------------------------------

    def test_member_state_independent_of_conversation_state(self):
        conversation = self._make_conversation("Conv Members")
        user2 = self.env["res.users"].create(
            {
                "name": "Second Member",
                "login": "second_member_test@example.com",
                "email": "second_member_test@example.com",
            }
        )
        member1 = self.Member.create(
            {"conversation_id": conversation.id, "user_id": self.user.id}
        )
        member2 = self.Member.create(
            {"conversation_id": conversation.id, "user_id": user2.id}
        )
        self.assertEqual(conversation.state, "open")

        member1.is_handled = True

        self.assertEqual(conversation.state, "open")
        self.assertFalse(member2.is_handled)

    # ------------------------------------------------------------
    # AC9 - internal vs outbound messages
    # ------------------------------------------------------------

    def test_internal_note_vs_outbound_message(self):
        conversation = self._make_conversation("Conv Messages")
        note = conversation.message_post(
            body="An internal note", subtype_xmlid="mail.mt_note"
        )
        self.assertEqual(note.subtype_id, self.env.ref("mail.mt_note"))
        self.assertFalse(note.transport_id)

        transport = self.env["conversation.transport"].create(
            {"name": "Test Email Transport"}
        )
        outbound = conversation.message_post(
            body="An outbound reply", subtype_xmlid="mail.mt_comment"
        )
        outbound.transport_id = transport

        self.assertTrue(outbound.transport_id)
        self.assertNotEqual(outbound.subtype_id, self.env.ref("mail.mt_note"))

    # ------------------------------------------------------------
    # AC4 - bare-email dedup
    # ------------------------------------------------------------

    def test_bare_email_dedup_and_lazy_partner_link(self):
        conversation = self._make_conversation("Conv Dedup")
        p1 = self.Participant._get_or_create(
            conversation, "Someone@Example.com"
        )
        p2 = self.Participant._get_or_create(
            conversation, "  someone@example.com  "
        )
        self.assertEqual(p1, p2)
        participants = self.Participant.search(
            [("conversation_id", "=", conversation.id)]
        )
        self.assertEqual(len(participants), 1)
        self.assertFalse(p1.partner_id)
        self.assertEqual(p1.email_normalized, "someone@example.com")

        p3 = self.Participant._get_or_create(
            conversation, "someone@example.com", partner=self.partner_a
        )
        self.assertEqual(p3, p1)
        self.assertEqual(p1.partner_id, self.partner_a)

    # ------------------------------------------------------------
    # View build smoke
    # ------------------------------------------------------------

    def test_conversation_form_smoke(self):
        team = self.env["mail.conversation.team"].create({"name": "Smoke Team"})
        form = Form(self.Conversation)
        form.name = "Smoke Conversation"
        form.team_id = team
        conversation = form.save()
        self.assertEqual(conversation.name, "Smoke Conversation")
        self.assertEqual(conversation.team_id, team)

    def test_conversation_team_form_smoke(self):
        form = Form(self.env["mail.conversation.team"])
        form.name = "Smoke Team 2"
        team = form.save()
        self.assertEqual(team.name, "Smoke Team 2")

    def test_conversation_list_views_buildable(self):
        # Instantiating list views: a missing/renamed field on the arch
        # raises at view-validation/render time.
        self.Conversation.get_views([(None, "list")])
        self.env["mail.conversation.team"].get_views([(None, "list")])
