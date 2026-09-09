# -*- coding: utf-8 -*-
# Acceptance criteria (task 3633):
#   AC-1: An alias flagged track_utm_source with source X exposes those defaults
#         (track off, or no source -> no defaults). [_get_utm_creation_values]
#   AC-2: A record created from inbound mail to a tracking alias is stamped with
#         source X (and medium/campaign when set) — end-to-end via message_process.
#   AC-3: An explicit alias_defaults source wins over the configured field
#         (we never overwrite a value the caller already provided).
#   AC-4: Converting/creating a lead from that ticket carries source X to the
#         lead (Enterprise helpdesk.ticket.to.lead wizard, end-to-end).

from odoo.addons.mail.tests.common import MailCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestAliasUtmTracking(MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # MailCommon sets up cls.mail_alias_domain (a mail.alias.domain) and the
        # mail gateway, so inbound message_process can route by recipient.
        cls.source_x = cls.env["utm.source"].create({"name": "Alias Source X"})
        cls.source_y = cls.env["utm.source"].create({"name": "Alias Source Y"})
        cls.medium = cls.env["utm.medium"].create({"name": "Alias Medium"})
        cls.campaign = cls.env["utm.campaign"].create({"name": "Alias Campaign"})

        cls.team = cls.env["helpdesk.team"].create(
            {"name": "UTM Test Team", "use_alias": False}
        )
        ticket_model = cls.env["ir.model"]._get("helpdesk.ticket")

        # Alias -> helpdesk.ticket, flagged to track source X (+ medium/campaign).
        cls.alias = cls.env["mail.alias"].create(
            {
                "alias_name": "utm-track-team",
                "alias_model_id": ticket_model.id,
                "alias_domain_id": cls.mail_alias_domain.id,
                "alias_defaults": "{'team_id': %s}" % cls.team.id,
                "track_utm_source": True,
                "utm_source_id": cls.source_x.id,
                "utm_medium_id": cls.medium.id,
                "utm_campaign_id": cls.campaign.id,
            }
        )
        cls.alias_email = "%s@%s" % (cls.alias.alias_name, cls.mail_alias_domain.name)

    def _inbound(self, to=None, msg_id="<utm-3633@test>"):
        """Push a plain inbound email to `to` (defaults to the tracking alias)
        through the mail gateway and return the created helpdesk.ticket."""
        to = to or self.alias_email
        mime = (
            "MIME-Version: 1.0\n"
            "Date: Thu, 27 Dec 2018 16:27:45 +0100\n"
            "Message-ID: %s\n"
            "Subject: I need help\n"
            "From: Client UTM <client_utm@example.com>\n"
            "To: %s\n"
            'Content-Type: text/plain; charset="UTF-8"\n'
            "\n"
            "Please help me.\n"
        ) % (msg_id, to)
        ticket_id = (
            self.env["mail.thread"].sudo().message_process(False, mime)
        )
        return self.env["helpdesk.ticket"].browse(ticket_id)

    # ---- AC-1: alias creation-values builder --------------------------------

    def test_creation_values_when_tracking(self):
        """AC-1: a tracking alias returns its UTM defaults keyed by record field."""
        self.assertEqual(
            self.alias._get_utm_creation_values(),
            {
                "source_id": self.source_x.id,
                "medium_id": self.medium.id,
                "campaign_id": self.campaign.id,
            },
        )

    def test_creation_values_when_tracking_off(self):
        """AC-1: tracking off -> no defaults even if a source is set."""
        self.alias.track_utm_source = False
        self.assertEqual(self.alias._get_utm_creation_values(), {})

    def test_creation_values_when_no_source(self):
        """AC-1: tracking on but no source -> no defaults (source is the trigger)."""
        self.alias.utm_source_id = False
        self.assertEqual(self.alias._get_utm_creation_values(), {})

    def test_creation_values_source_only(self):
        """AC-1: medium/campaign are optional; source alone is enough."""
        self.alias.utm_medium_id = False
        self.alias.utm_campaign_id = False
        self.assertEqual(
            self.alias._get_utm_creation_values(),
            {"source_id": self.source_x.id},
        )

    # ---- AC-2: inbound mail -> ticket gets the alias source -----------------

    def test_inbound_mail_creates_ticket_with_source(self):
        """AC-2 (end-to-end): an email to the tracking alias yields a ticket
        attributed to source X (+ medium/campaign), with unrelated alias_defaults
        (team_id) preserved."""
        ticket = self._inbound()
        self.assertTrue(ticket.exists(), "inbound mail should create a ticket")
        self.assertEqual(ticket.team_id, self.team, "team_id alias_default preserved")
        self.assertEqual(
            ticket.source_id, self.source_x, "ticket must carry the alias UTM source"
        )
        self.assertEqual(ticket.medium_id, self.medium)
        self.assertEqual(ticket.campaign_id, self.campaign)
        return ticket

    def test_inbound_no_source_when_tracking_off(self):
        """AC-2 (negative): a non-tracking alias does not stamp any source."""
        self.alias.track_utm_source = False
        ticket = self._inbound(msg_id="<utm-3633-off@test>")
        self.assertTrue(ticket.exists())
        self.assertFalse(ticket.source_id, "no source should be stamped when off")

    def test_inbound_explicit_alias_default_wins(self):
        """AC-3: an explicit source_id in alias_defaults is not overwritten by
        the configured utm_source_id."""
        self.alias.alias_defaults = "{'team_id': %s, 'source_id': %s}" % (
            self.team.id,
            self.source_y.id,
        )
        ticket = self._inbound(msg_id="<utm-3633-explicit@test>")
        self.assertTrue(ticket.exists())
        self.assertEqual(
            ticket.source_id,
            self.source_y,
            "explicit alias_defaults source must win over the configured field",
        )

    # ---- AC-4: ticket -> lead carries the source ----------------------------

    def test_ticket_to_lead_carries_source(self):
        """AC-4 (end-to-end): converting the inbound-created ticket to a lead
        carries source X (+ medium/campaign) to the lead."""
        ticket = self.test_inbound_mail_creates_ticket_with_source()
        # group_use_lead so the wizard produces a lead (vs an opportunity).
        self.env.user.groups_id += self.env.ref("crm.group_use_lead")
        wizard = (
            self.env["helpdesk.ticket.to.lead"]
            .with_context(active_id=ticket.id, active_model="helpdesk.ticket")
            .create({"ticket_id": ticket.id})
        )
        action = wizard.action_convert_to_lead()
        lead = self.env["crm.lead"].browse(action["res_id"])
        self.assertTrue(lead.exists(), "wizard should create a lead")
        self.assertEqual(
            lead.source_id, self.source_x, "lead must inherit the ticket's UTM source"
        )
        self.assertEqual(lead.medium_id, self.medium)
        self.assertEqual(lead.campaign_id, self.campaign)
