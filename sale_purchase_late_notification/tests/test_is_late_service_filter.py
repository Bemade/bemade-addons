# Copyright 2026 Bemade Inc. (Marc Durepos <marc@bemade.org>, https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""
Tests for the product-type guard added to sale.order.line.is_late.

Acceptance criteria:
1. A service-type line that is undelivered, on a confirmed SO, with an expected_ship_date
   in the past is is_late == False (the guard suppresses it).
2. A consu (deliverable) line, undelivered, confirmed, with expected_ship_date in the past,
   is still is_late == True (the fix doesn't over-suppress real late deliverables).
3. Search/compute parity: search([('is_late','=',True)]) returns the consu line and excludes
   the service line, and each line's is_late compute matches its search membership.
4. SO rollup smoke: order.is_late (any(order_line.is_late)) is driven only by the consu line.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIsLateServiceFilter(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env["res.partner"].create(
            {"name": "Test Customer Service Filter"}
        )
        cls.product_consu = cls.env["product.product"].create(
            {"name": "Test Consu Product", "type": "consu"}
        )
        cls.product_service = cls.env["product.product"].create(
            {"name": "Test Service Product", "type": "service"}
        )

    def _create_confirmed_so_with_line(self, product, expected_ship_date):
        """
        Create a confirmed SO with a single line for the given product,
        then manually set expected_ship_date on that line.
        """
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "client_order_ref": "test-service-filter",
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 50,
                        },
                    )
                ],
            }
        )
        order.with_context(skip_tax_warning=True).action_confirm()
        order.order_line.expected_ship_date = expected_ship_date
        return order

    def test_service_line_not_late_when_overdue(self):
        """
        Criterion 1: a past-due undelivered service line is NOT flagged as is_late.
        """
        past_date = fields.Date.today() - timedelta(days=3)
        order = self._create_confirmed_so_with_line(self.product_service, past_date)
        line = order.order_line
        self.assertFalse(
            line.is_late,
            "A past-due service line should NOT be flagged as is_late (service guard).",
        )

    def test_consu_line_is_late_when_overdue(self):
        """
        Criterion 2: a past-due undelivered consu line IS flagged as is_late.
        """
        past_date = fields.Date.today() - timedelta(days=3)
        order = self._create_confirmed_so_with_line(self.product_consu, past_date)
        line = order.order_line
        self.assertTrue(
            line.is_late,
            "A past-due consu line should still be flagged as is_late.",
        )

    def test_search_compute_parity(self):
        """
        Criterion 3: search([('is_late','=',True)]) returns the consu line and excludes
        the service line; each line's is_late compute matches its search membership.
        """
        past_date = fields.Date.today() - timedelta(days=3)

        order_consu = self._create_confirmed_so_with_line(self.product_consu, past_date)
        order_service = self._create_confirmed_so_with_line(
            self.product_service, past_date
        )

        consu_line = order_consu.order_line
        service_line = order_service.order_line

        # Search for lines where is_late = True
        late_lines = self.env["sale.order.line"].search([("is_late", "=", True)])

        self.assertIn(
            consu_line,
            late_lines,
            "consu line should appear in search([('is_late','=',True)]).",
        )
        self.assertNotIn(
            service_line,
            late_lines,
            "service line should NOT appear in search([('is_late','=',True)]).",
        )

        # Verify compute values are consistent with search results
        self.assertTrue(
            consu_line.is_late,
            "consu_line.is_late compute should be True (consistent with search).",
        )
        self.assertFalse(
            service_line.is_late,
            "service_line.is_late compute should be False (consistent with search).",
        )

        # Also verify search for is_late = False
        not_late_lines = self.env["sale.order.line"].search([("is_late", "=", False)])
        self.assertIn(
            service_line,
            not_late_lines,
            "service line should appear in search([('is_late','=',False)]).",
        )
        self.assertNotIn(
            consu_line,
            not_late_lines,
            "consu line should NOT appear in search([('is_late','=',False)]).",
        )

    def test_so_rollup_service_only_not_late(self):
        """
        Criterion 4a: an SO with only a past-due service line is NOT rolled up as is_late.
        """
        past_date = fields.Date.today() - timedelta(days=3)
        order = self._create_confirmed_so_with_line(self.product_service, past_date)
        self.assertFalse(
            order.is_late,
            "An SO with only a past-due service line should NOT be marked as is_late "
            "(Nicolas's exact complaint).",
        )

    def test_so_rollup_consu_makes_so_late(self):
        """
        Criterion 4b: adding a past-due consu line to a SO makes the SO is_late = True,
        even if a service line is also present.
        """
        past_date = fields.Date.today() - timedelta(days=3)

        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "client_order_ref": "test-rollup",
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_service.id,
                            "product_uom_qty": 1,
                            "price_unit": 10,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_consu.id,
                            "product_uom_qty": 1,
                            "price_unit": 100,
                        },
                    ),
                ],
            }
        )
        order.with_context(skip_tax_warning=True).action_confirm()

        # Set both lines to past expected_ship_date
        for line in order.order_line:
            line.expected_ship_date = past_date

        self.assertTrue(
            order.is_late,
            "An SO with a past-due consu line (and a service line) should be is_late = True.",
        )
