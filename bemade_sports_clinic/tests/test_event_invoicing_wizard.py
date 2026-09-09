# Acceptance criteria:
# - When the single-event "Add to SO" wizard creates a new sale.order, date_order is set to
#   the event's start date (not today/now).
# - When an existing draft SO is used, its date_order is not changed by the wizard.
# - When the batch "Add to SO" wizard creates a new sale.order, date_order is set to the
#   earliest event start date among the events being processed for that partner.
# - SO line descriptions use the local date of the event start, not the UTC date.
#   (An event starting 8 PM EST on Nov 4 is midnight UTC on Nov 5 — must show Nov 4.)

import datetime
from datetime import timedelta

import pytz

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestEventInvoicingWizardDate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.organization = cls.env["res.partner"].create({"name": "Test Org", "is_company": True})
        cls.team = cls.env["sports.team"].create({
            "name": "Test Team",
            "parent_id": cls.organization.id,
        })

        cls.coverage_product = cls.env["product.product"].create({
            "name": "Coverage",
            "type": "service",
            "uom_id": cls.env.ref("uom.product_uom_hour").id,
        })
        cls.travel_product = cls.env["product.product"].create({
            "name": "Travel",
            "type": "service",
            "uom_id": cls.env.ref("uom.product_uom_hour").id,
        })
        cls.clinic_product = cls.env["product.product"].create({
            "name": "Clinic",
            "type": "service",
            "uom_id": cls.env.ref("uom.product_uom_hour").id,
        })

        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("bemade_sports_clinic.product_event_coverage_customer_id", cls.coverage_product.id)
        ICP.set_param("bemade_sports_clinic.product_event_travel_customer_id", cls.travel_product.id)
        ICP.set_param("bemade_sports_clinic.product_event_clinic_customer_id", cls.clinic_product.id)

        cls.therapist_user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Test Therapist",
            "login": "therapist.invoice.test@example.com",
            "groups_id": [Command.link(cls.env.ref("base.group_user").id)],
        })

        past_start = fields.Datetime.now() - timedelta(days=7, hours=2)
        past_end = past_start + timedelta(hours=2)

        cls.event = cls.env["sports.event"].create({
            "name": "Test Event",
            "team_ids": [Command.link(cls.team.id)],
            "date_start": past_start,
            "date_end": past_end,
        })

        cls.timesheet = cls.env["sports.event.timesheet"].create({
            "event_id": cls.event.id,
            "user_id": cls.therapist_user.id,
            "coverage_duration": 2.0,
        })

    def test_new_so_date_order_is_event_start_date(self):
        """When no draft SO exists, the created SO's date_order matches the event start date."""
        wizard = self.env["sports.event.invoicing.wizard"].with_context(
            active_id=self.event.id
        ).create({"event_id": self.event.id})
        wizard.action_process()

        so = self.env["sale.order"].search(
            [("partner_id", "=", self.organization.id)], limit=1
        )
        self.assertTrue(so, "A sale order should have been created")
        self.assertEqual(
            so.date_order.date(),
            self.event.date_start.date(),
            "SO date_order should equal the event start date, not today",
        )

    def test_existing_so_date_order_is_not_changed(self):
        """When an existing draft SO is used, its date_order is preserved."""
        original_date = fields.Datetime.now() - timedelta(days=30)
        existing_so = self.env["sale.order"].create({
            "partner_id": self.organization.id,
            "date_order": original_date,
        })

        extra_ts = self.env["sports.event.timesheet"].create({
            "event_id": self.event.id,
            "user_id": self.therapist_user.id,
            "coverage_duration": 1.0,
        })
        wizard = self.env["sports.event.invoicing.wizard"].with_context(
            active_id=self.event.id
        ).create({
            "event_id": self.event.id,
            "customer_sale_order_id": existing_so.id,
        })
        wizard.action_process()

        existing_so.invalidate_recordset()
        self.assertEqual(
            existing_so.date_order.date(),
            original_date.date(),
            "Existing SO date_order should not be modified by the wizard",
        )

    def test_batch_wizard_new_so_uses_earliest_event_start_date(self):
        """Batch wizard dates the new SO to the earliest event start among the selected events."""
        earlier_start = self.event.date_start - timedelta(days=3)
        earlier_event = self.env["sports.event"].create({
            "name": "Earlier Event",
            "team_ids": [Command.link(self.team.id)],
            "date_start": earlier_start,
            "date_end": earlier_start + timedelta(hours=2),
        })
        self.env["sports.event.timesheet"].create({
            "event_id": earlier_event.id,
            "user_id": self.therapist_user.id,
            "coverage_duration": 1.5,
        })

        wizard = self.env["sports.event.batch_invoicing.wizard"].with_context(
            active_ids=[self.event.id, earlier_event.id]
        ).create({
            "event_ids": [Command.set([self.event.id, earlier_event.id])],
        })
        wizard.action_process()

        so = self.env["sale.order"].search(
            [("partner_id", "=", self.organization.id)], order="id desc", limit=1
        )
        self.assertTrue(so, "A sale order should have been created")
        self.assertEqual(
            so.date_order.date(),
            earlier_start.date(),
            "Batch SO date_order should be the earliest event start date",
        )

    def test_so_line_description_uses_local_date_not_utc(self):
        """Event starting 8 PM EST (= midnight+1h UTC next day) must appear in the
        description as the local date, not the UTC date."""
        est = pytz.timezone("America/Toronto")
        # Nov 4 2025 20:00 EST = Nov 5 2025 01:00 UTC — raw .date() gives Nov 5 (wrong)
        local_evening = est.localize(datetime.datetime(2025, 11, 4, 20, 0, 0))
        utc_start = local_evening.astimezone(pytz.utc).replace(tzinfo=None)
        utc_end = utc_start + timedelta(hours=2)

        event = self.env["sports.event"].create({
            "name": "Evening Game",
            "team_ids": [Command.link(self.team.id)],
            "date_start": utc_start,
            "date_end": utc_end,
        })
        self.env["sports.event.timesheet"].create({
            "event_id": event.id,
            "user_id": self.therapist_user.id,
            "coverage_duration": 2.0,
        })

        # Run the wizard with America/Toronto timezone in context
        wizard = self.env["sports.event.invoicing.wizard"].with_context(
            active_id=event.id, tz="America/Toronto"
        ).create({"event_id": event.id})
        wizard.action_process()

        sol = self.env["sale.order.line"].search(
            [("order_id.partner_id", "=", self.organization.id)], order="id desc", limit=1
        )
        self.assertTrue(sol, "A sale order line should have been created")
        self.assertIn(
            "2025-11-04",
            sol.name,
            "Description should contain the local date (Nov 4), not the UTC date (Nov 5)",
        )
