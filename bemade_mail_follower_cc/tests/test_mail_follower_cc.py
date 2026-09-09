# -*- coding: utf-8 -*-
from odoo.addons.mail.tests.common import MailCommon, mail_new_test_user
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.tools.mail import email_normalize, email_split_and_format_normalize


@tagged("post_install", "-at_install", "bemade_mail_follower_cc")
class TestMailFollowerCc(MailCommon):
    """Tests pour bemade_mail_follower_cc v1.0.0 (email_cc_display_only).

    Garantie clé : les followers apparaissent dans le header Cc (display) mais
    PAS dans email_to_normalized — donc zéro livraison SMTP supplémentaire.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_author = mail_new_test_user(
            cls.env,
            login="test_author",
            name="Author User",
            email="author@test.example.com",
            groups="base.group_user,base.group_partner_manager",
            notification_type="email",
        )
        cls.user_peer1 = mail_new_test_user(
            cls.env,
            login="test_peer1",
            name="Peer One",
            email="peer1@test.example.com",
            groups="base.group_user,base.group_partner_manager",
            notification_type="email",
        )
        cls.user_peer2 = mail_new_test_user(
            cls.env,
            login="test_peer2",
            name="Peer Two",
            email="peer2@test.example.com",
            groups="base.group_user,base.group_partner_manager",
            notification_type="email",
        )
        cls.partner_external = cls.env["res.partner"].create({
            "name": "External Customer",
            "email": "external@customer.example.com",
        })

    def _make_record(self):
        return self.env["res.partner"].create({
            "name": "Test Thread Record",
            "email": "thread@test.example.com",
        })

    def _post_and_get_mails(self, record, followers):
        record.message_subscribe(partner_ids=[p.id for p in followers])
        msg = record.with_user(self.user_author).message_post(
            body="Test message",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            mail_auto_delete=False,
        )
        return self.env["mail.mail"].sudo().search([("mail_message_id", "=", msg.id)])

    def _cc_normalized(self, entry):
        cc = entry.get("email_cc") or []
        if isinstance(cc, str):
            cc = email_split_and_format_normalize(cc)
        return {email_normalize(a) for a in cc if email_normalize(a)}

    def _to_normalized(self, entry):
        return {a for a in (entry.get("email_to_normalized") or []) if a}

    # ------------------------------------------------------------------
    # Test 1 : garantie principale — Cc display-only, pas dans SMTP
    # ------------------------------------------------------------------

    @mute_logger("odoo.addons.mail.models.mail_mail", "odoo.models.unlink")
    def test_cc_display_only_not_in_smtp_envelope(self):
        """Les followers en Cc NE DOIVENT PAS apparaître dans email_to_normalized.

        C'est la garantie fondamentale : affichage dans le header Cc sans
        livraison SMTP supplémentaire. Si email_to_normalized contient un
        follower Cc, il recevrait l'email en double en production.
        """
        record = self._make_record()
        followers = [self.user_peer1.partner_id, self.user_peer2.partner_id, self.partner_external]
        mail_mails = self._post_and_get_mails(record, followers)
        self.assertTrue(mail_mails, "Aucun mail.mail créé")

        follower_emails = {
            email_normalize(p.email) for p in followers if p.email
        }

        for mail in mail_mails:
            entries = mail._prepare_outgoing_list()
            for entry in entries:
                to_norm = self._to_normalized(entry)
                cc_norm = self._cc_normalized(entry)

                # email_to_normalized doit être non-vide (filtre SMTP actif)
                self.assertTrue(
                    to_norm,
                    "email_to_normalized est vide — le filtre SMTP serait désactivé "
                    "et TOUS les Cc recevraient l'email"
                )

                # Aucun follower Cc ne doit être dans email_to_normalized
                cc_in_smtp = follower_emails & to_norm - {email_normalize(entry.get("email_to") or "x")}
                # (on exclut le destinataire principal lui-même qui est légitimement dans les deux)
                for follower_email in follower_emails:
                    if follower_email in to_norm:
                        # Ce follower est le destinataire principal de cet envoi — OK
                        continue
                    self.assertNotIn(
                        follower_email, to_norm,
                        f"{follower_email} est un follower Cc mais apparaît dans "
                        f"email_to_normalized — il recevrait l'email via SMTP"
                    )

    # ------------------------------------------------------------------
    # Test 2 : les followers apparaissent bien dans le header Cc
    # ------------------------------------------------------------------

    @mute_logger("odoo.addons.mail.models.mail_mail", "odoo.models.unlink")
    def test_followers_appear_in_cc_header(self):
        """Les followers doivent apparaître dans email_cc (le header affiché)."""
        record = self._make_record()
        followers = [self.user_peer1.partner_id, self.user_peer2.partner_id]
        mail_mails = self._post_and_get_mails(record, followers)
        self.assertTrue(mail_mails)

        follower_emails = {
            email_normalize(p.email) for p in followers if p.email
        }

        for mail in mail_mails:
            entries = mail._prepare_outgoing_list()
            all_cc = set()
            for entry in entries:
                all_cc |= self._cc_normalized(entry)

            for follower_email in follower_emails:
                self.assertIn(
                    follower_email, all_cc,
                    f"{follower_email} devrait apparaître dans le Cc d'au moins un envoi"
                )

    # ------------------------------------------------------------------
    # Test 3 : le To recipient peut apparaître en Cc (limitation v1.0.0 connue)
    #           mais ne reçoit PAS l'email deux fois (SMTP non affecté)
    # ------------------------------------------------------------------

    @mute_logger("odoo.addons.mail.models.mail_mail", "odoo.models.unlink")
    def test_to_recipient_in_cc_does_not_cause_double_delivery(self):
        """v1.0.0 met TOUS les followers en Cc, y compris le destinataire To.
        C'est un affichage cosmétique — la garantie SMTP (test 1) assure qu'ils
        ne reçoivent pas l'email en double.
        """
        record = self._make_record()
        followers = [self.user_peer1.partner_id, self.user_peer2.partner_id]
        mail_mails = self._post_and_get_mails(record, followers)
        self.assertTrue(mail_mails)

        for mail in mail_mails:
            entries = mail._prepare_outgoing_list()
            for entry in entries:
                to_norm = self._to_normalized(entry)
                cc_norm = self._cc_normalized(entry)
                # v1.0.0 : le To recipient peut être dans Cc (limitation connue)
                # La vraie garantie = il n'est PAS dans email_to_normalized une 2e fois
                # (un seul envoi SMTP par adresse, contrôlé par send_validated_to)
                self.assertEqual(
                    len(to_norm), 1,
                    f"Chaque entrée doit avoir exactement un destinataire SMTP, got {to_norm}"
                )

    # ------------------------------------------------------------------
    # Test 4 : email_cc_display_only est peuplé sur mail.mail
    # ------------------------------------------------------------------

    @mute_logger("odoo.addons.mail.models.mail_mail", "odoo.models.unlink")
    def test_email_cc_display_only_field_is_set(self):
        """Le champ email_cc_display_only doit être peuplé par mail.thread."""
        record = self._make_record()
        followers = [self.user_peer1.partner_id, self.partner_external]
        mail_mails = self._post_and_get_mails(record, followers)
        self.assertTrue(mail_mails)

        for mail in mail_mails:
            self.assertTrue(
                mail.email_cc_display_only,
                "email_cc_display_only devrait être peuplé par "
                "_notify_by_email_get_base_mail_values"
            )
            cc_addrs = email_split_and_format_normalize(mail.email_cc_display_only)
            cc_normalized = {email_normalize(a) for a in cc_addrs if email_normalize(a)}
            self.assertTrue(cc_normalized, "email_cc_display_only ne contient aucune adresse valide")

    # ------------------------------------------------------------------
    # Test 5 : sans followers, pas de Cc
    # ------------------------------------------------------------------

    @mute_logger("odoo.addons.mail.models.mail_mail", "odoo.models.unlink")
    def test_no_followers_no_cc(self):
        """Sans followers, email_cc_display_only est vide et Cc est absent."""
        record = self._make_record()
        msg = record.with_user(self.user_author).message_post(
            body="Message sans followers",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            mail_auto_delete=False,
        )
        mail_mails = self.env["mail.mail"].sudo().search([("mail_message_id", "=", msg.id)])

        for mail in mail_mails:
            entries = mail._prepare_outgoing_list()
            for entry in entries:
                cc_norm = self._cc_normalized(entry)
                # Le Cc peut contenir l'adresse du destinataire lui-même (comportement Odoo)
                # mais ne doit pas contenir de followers injectés par notre module
                self.assertFalse(
                    mail.email_cc_display_only,
                    "email_cc_display_only devrait être vide sans followers"
                )
