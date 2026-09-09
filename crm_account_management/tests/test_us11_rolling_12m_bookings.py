# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""
US-11 (task 3751): Rolling-12m dashboard figure reflects confirmed-order bookings.

Acceptance criteria
-------------------
1. rolling_12m_sales shows confirmed-order bookings for the trailing 12 months
   (today - 12 months -> today), measured by date_order.
2. rolling_12m_sales_prior covers the full prior window (today - 24 months ->
   today - 12 months), measured by date_order.
3. The figures reconcile against confirmed sale.order amounts in each window
   (a tester can cross-check the dashboard number against the sum of confirmed
   orders), and unconfirmed (draft) orders are excluded from both windows.
4. rolling_12m_change_pct == (trailing - prior) / prior.
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests import tagged

from odoo.addons.crm_account_management.tests.common import OUTestCommon


@tagged("post_install", "-at_install")
class TestUS11Rolling12mBookings(OUTestCommon):
    """Rolling-12m metrics aggregate confirmed sale.order by date_order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]
        cls.product = cls.env["product.product"].create(
            {
                "name": "Rolling12m Test Product",
                "list_price": 100.0,
            }
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_company(self, name):
        """Create a top-level company partner (triggers OU auto-create)."""
        partner = self.partner_model.create({"name": name, "is_company": True})
        ou = self.ou_model.search([("owner_id", "=", partner.id)], limit=1)
        return partner, ou

    def _make_order(self, partner, amount, order_date, confirm=True):
        """Create a sale.order, confirm it, then force date_order into the window.

        ``action_confirm()`` resets ``date_order`` to now, so the desired date
        is written *after* confirmation (the established test_us02 pattern) —
        otherwise every order lands in the trailing window and the windowing
        assertions become meaningless.
        """
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "price_unit": amount,
                            "tax_id": False,
                        },
                    )
                ],
            }
        )
        if confirm:
            order.action_confirm()
        order.date_order = order_date
        return order

    # ------------------------------------------------------------------
    # Test
    # ------------------------------------------------------------------

    def test_rolling_12m_bookings_windows_and_change(self):
        """AC1-4: trailing/prior windows, draft exclusion, change percentage."""
        partner, ou = self._make_company("Rolling12m Partner")
        today = date.today()

        # Trailing window (today-12m, today]: order ~6 months ago.
        trailing_date = today - relativedelta(months=6)
        self._make_order(partner, 300.0, trailing_date)

        # Prior window (today-24m, today-12m]: order ~18 months ago.
        prior_date = today - relativedelta(months=18)
        self._make_order(partner, 200.0, prior_date)

        # Draft control inside the trailing window — must be excluded (not confirmed).
        self._make_order(partner, 999.0, trailing_date, confirm=False)

        ou.invalidate_recordset()

        # AC1 + AC3: trailing figure equals the single confirmed trailing order,
        # and the draft order is excluded.
        self.assertAlmostEqual(
            ou.rolling_12m_sales,
            300.0,
            places=2,
            msg="rolling_12m_sales must equal the confirmed trailing-window booking "
            "(draft excluded).",
        )
        # AC2 + AC3: prior figure equals the single confirmed prior order.
        self.assertAlmostEqual(
            ou.rolling_12m_sales_prior,
            200.0,
            places=2,
            msg="rolling_12m_sales_prior must equal the confirmed prior-window booking.",
        )
        # AC4: change percentage as a decimal.
        self.assertAlmostEqual(
            ou.rolling_12m_change_pct,
            (300.0 - 200.0) / 200.0,
            places=4,
            msg="rolling_12m_change_pct must be (trailing - prior) / prior.",
        )

    def test_rolling_12m_excludes_out_of_window_orders(self):
        """Confirmed orders older than 24 months are excluded from both windows."""
        partner, ou = self._make_company("Rolling12m Out-Of-Window Partner")
        today = date.today()

        # Confirmed order 30 months ago — before the prior window's start.
        self._make_order(partner, 500.0, today - relativedelta(months=30))

        ou.invalidate_recordset()
        self.assertAlmostEqual(
            ou.rolling_12m_sales, 0.0, places=2,
            msg="Orders before the 24-month horizon must not count toward trailing.",
        )
        self.assertAlmostEqual(
            ou.rolling_12m_sales_prior, 0.0, places=2,
            msg="Orders before the 24-month horizon must not count toward prior.",
        )
