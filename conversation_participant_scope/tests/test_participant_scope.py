from odoo.tests import Form, TransactionCase


class TestParticipantScopeStub(TransactionCase):
    """Placeholder: kept so a minimal, dependency-free check always
    collects even if the behavioral suite (AC1-AC5) below needs
    adjustment.
    """

    def test_model_fields_registered(self):
        participant_fields = self.env["mail.conversation.participant"]._fields
        self.assertIn("receives_updates", participant_fields)
        self.assertIn("visibility", participant_fields)
        conversation_fields = self.env["mail.conversation"]._fields
        self.assertIn("external_visibility", conversation_fields)


class TestParticipantScope(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conversation = cls.env["mail.conversation"]
        cls.Partner = cls.env["res.partner"]
        # Distinct emails matter: mail.conversation.participant._get_or_create
        # dedups on email_normalized within a conversation, and a partner
        # with no email normalizes to the same NULL key as any other
        # emailless partner -- two emailless partners added to the SAME
        # conversation would collide onto a single participant record.
        cls.partner_p1 = cls.Partner.create(
            {"name": "Participant One", "email": "participant.one@example.com"}
        )
        cls.partner_p2 = cls.Partner.create(
            {"name": "Participant Two", "email": "participant.two@example.com"}
        )

    def _make_conversation(self, name="Test Conversation"):
        return self.Conversation.create({"name": name})

    # ------------------------------------------------------------
    # AC2 - future audience excludes CC-once, never subscribes
    # ------------------------------------------------------------

    def test_next_message_recipients_excludes_cc_once(self):
        conversation = self._make_conversation("Conv Audience")
        p1 = conversation._add_participant(partner=self.partner_p1)
        p2 = conversation._add_cc_once(partners=[self.partner_p2])
        p2 = p2[0]

        partners, email_to = conversation._next_message_recipients()

        self.assertIn(self.partner_p1, partners)
        self.assertNotIn(self.partner_p2, partners)
        self.assertFalse(email_to)
        self.assertFalse(conversation.message_follower_ids)
        # sanity: both records really are participants on the conversation
        self.assertEqual(p1.conversation_id, conversation)
        self.assertEqual(p2.conversation_id, conversation)

    # ------------------------------------------------------------
    # AC4 - raw email participant, no res.partner pollution
    # ------------------------------------------------------------

    def test_add_participant_raw_email_no_partner_pollution(self):
        conversation = self._make_conversation("Conv Raw Email")
        partner_count_before = self.Partner.search_count([])

        participant = conversation._add_participant(email="raw@x.test")

        partner_count_after = self.Partner.search_count([])
        self.assertFalse(participant.partner_id)
        self.assertEqual(participant.email_normalized, "raw@x.test")
        self.assertEqual(partner_count_after, partner_count_before)

        partners, email_to = conversation._next_message_recipients()
        self.assertFalse(partners)
        self.assertIn("raw@x.test", email_to)

    # ------------------------------------------------------------
    # AC3 - hide_internal visibility policy
    # ------------------------------------------------------------

    def test_participants_visible_to_hide_internal(self):
        conversation = self._make_conversation("Conv Hide Internal")
        conversation.external_visibility = "hide_internal"
        internal = conversation._add_participant(
            email="internal@example.com", kind="internal"
        )
        external_a = conversation._add_participant(
            partner=self.partner_p1, kind="external"
        )
        external_b = conversation._add_participant(
            email="extb@example.com", kind="external"
        )

        visible_to_a = conversation._participants_visible_to(self.partner_p1)
        self.assertEqual(visible_to_a, external_a | external_b)
        self.assertNotIn(internal, visible_to_a)

        visible_to_internal = conversation._participants_visible_to(False)
        self.assertEqual(
            visible_to_internal, internal | external_a | external_b
        )

    # ------------------------------------------------------------
    # AC3 - private visibility policy
    # ------------------------------------------------------------

    def test_participants_visible_to_private(self):
        conversation = self._make_conversation("Conv Private")
        conversation.external_visibility = "private"
        external_a = conversation._add_participant(
            partner=self.partner_p1, kind="external"
        )
        conversation._add_participant(
            partner=self.partner_p2, kind="external"
        )

        visible_to_a = conversation._participants_visible_to(self.partner_p1)
        self.assertEqual(visible_to_a, external_a)

        visible_to_internal = conversation._participants_visible_to(False)
        self.assertEqual(len(visible_to_internal), 2)

    # ------------------------------------------------------------
    # AC3 - per-participant override, applied last
    # ------------------------------------------------------------

    def test_participants_visible_to_per_participant_override(self):
        conversation = self._make_conversation("Conv Override")
        conversation.external_visibility = "hide_internal"
        internal_exposed = conversation._add_participant(
            email="internal-exposed@example.com",
            kind="internal",
            visibility="exposed",
        )
        external_a = conversation._add_participant(
            partner=self.partner_p1, kind="external"
        )
        external_hidden = conversation._add_participant(
            partner=self.partner_p2, kind="external", visibility="hidden"
        )

        visible_to_a = conversation._participants_visible_to(self.partner_p1)
        self.assertIn(internal_exposed, visible_to_a)
        self.assertIn(external_a, visible_to_a)
        self.assertNotIn(external_hidden, visible_to_a)

    # ------------------------------------------------------------
    # Promote CC-once to ongoing recipient
    # ------------------------------------------------------------

    def test_promote_to_recipient(self):
        conversation = self._make_conversation("Conv Promote")
        cc = conversation._add_cc_once(partners=[self.partner_p1])[0]
        self.assertFalse(cc.receives_updates)

        cc._promote_to_recipient()

        self.assertTrue(cc.receives_updates)
        partners, _email_to = conversation._next_message_recipients()
        self.assertIn(self.partner_p1, partners)

    # ------------------------------------------------------------
    # AC5 - view build smoke
    # ------------------------------------------------------------

    def test_conversation_form_smoke(self):
        conversation = self._make_conversation("Conv Form Smoke")
        conversation._add_participant(email="formsmoke@example.com")

        form = Form(conversation)
        with form.participant_ids.edit(0) as line:
            line.receives_updates = False
            line.visibility = "hidden"
        conversation = form.save()

        participant = conversation.participant_ids
        self.assertFalse(participant.receives_updates)
        self.assertEqual(participant.visibility, "hidden")
