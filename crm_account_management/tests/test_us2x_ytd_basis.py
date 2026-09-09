# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""
Task 3750 — Dashboard YTD metric basis: fiscal-YTD sales vs calendar-YTD bookings.

Acceptance criteria
-------------------
1. A res.config.settings selection (ytd_metric_basis) selects the dashboard YTD
   metric: fiscal-YTD sales (current behaviour) vs calendar-YTD bookings.
2. In bookings mode, ytd_sales is the confirmed-order (state='sale') amount from
   Jan 1 of the current calendar year to today; ytd_sales_prior_year is the same
   calendar window last year (Jan 1 prior year -> same month/day prior year).
3. The basis is stored system-wide (ir.config_parameter) and respected by the
   stored dashboard computation.
4. Default (fiscal) leaves the dashboard behaving exactly as today (no regression).
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests import tagged

from odoo.addons.crm_account_management.tests.common import OUTestCommon


@tagged("post_install", "-at_install")
class TestYTDMetricBasis(OUTestCommon):
    """Branch coverage for _compute_sales_metrics on ytd_metric_basis."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]
        cls.param = cls.env["ir.config_parameter"].sudo()
        cls.param_key = "crm_account_management.ytd_metric_basis"

        cls.product = cls.env["product.product"].create(
            {"name": "YTD Basis Test Product", "list_price": 100.0}
        )

        # Foreign currency for the mixed-currency bookings test:
        # 1 EUR = 1.25 company-currency (rate stored as 1/1.25 = 0.8).
        cls.foreign_currency = cls.setup_other_currency(
            "EUR", rates=[("2000-01-01", 0.8)]
        )

    def setUp(self):
        super().setUp()
        # Each test owns the global basis; reset to the default afterwards so
        # tests don't leak the config param into one another.
        self.addCleanup(self.param.set_param, self.param_key, "fiscal")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_company(self, name):
        partner = self.partner_model.create({"name": name, "is_company": True})
        ou = self.ou_model.search([("owner_id", "=", partner.id)], limit=1)
        return partner, ou

    def _make_confirmed_order(self, partner, amount, currency=None, order_date=None):
        """Create and confirm a sale.order with one line of ``amount``.

        In Odoo 18, sale.order.currency_id is computed from the pricelist, so a
        non-default currency is applied via a throwaway pricelist.

        ``action_confirm()`` resets ``date_order`` to now, so the desired date is
        written *after* confirmation (the established test_us02/test_us11
        pattern) — otherwise every order lands in the current window and the
        calendar-window assertions become meaningless.
        """
        if order_date is None:
            order_date = date.today()
        vals = {
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
        if currency:
            pricelist = self.env["product.pricelist"].create(
                {"name": f"PL {currency.name}", "currency_id": currency.id}
            )
            vals["pricelist_id"] = pricelist.id
        order = self.env["sale.order"].create(vals)
        order.action_confirm()
        order.date_order = order_date
        return order

    def _make_posted_invoice(self, partner, amount, invoice_date=None):
        if invoice_date is None:
            invoice_date = date.today()
        invoice = self.env["account.move"].create(
            {
                "partner_id": partner.id,
                "move_type": "out_invoice",
                "invoice_date": invoice_date,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": False,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    # ------------------------------------------------------------------
    # AC-4: default (fiscal) is unchanged — invoice-driven figure
    # ------------------------------------------------------------------

    def test_default_fiscal_uses_invoices(self):
        """With the param unset (default fiscal), ytd_sales is the posted-invoice
        total and ignores confirmed sale orders."""
        self.param.set_param(self.param_key, "")  # absent => fiscal
        partner, ou = self._make_company("Fiscal Default Co")

        self._make_posted_invoice(partner, 1000.0)
        # A confirmed SO of a different amount must NOT contribute in fiscal mode.
        self._make_confirmed_order(partner, 7777.0)

        ou.invalidate_recordset()
        self.assertAlmostEqual(
            ou.ytd_sales,
            1000.0,
            places=2,
            msg="Fiscal default must equal the posted-invoice total, not the SO booking.",
        )

    # ------------------------------------------------------------------
    # AC-1/AC-2: bookings mode switches the figure to confirmed SOs
    # ------------------------------------------------------------------

    def test_bookings_uses_confirmed_orders_not_invoices(self):
        """In bookings mode, ytd_sales equals the confirmed-SO total, NOT the
        posted-invoice total — proving the branch is live and SO-driven."""
        self.param.set_param(self.param_key, "bookings")
        partner, ou = self._make_company("Bookings Co")

        # Invoice and SO of clearly different amounts.
        self._make_posted_invoice(partner, 1000.0)
        self._make_confirmed_order(partner, 2500.0)

        ou.invalidate_recordset()
        self.assertAlmostEqual(
            ou.ytd_sales,
            2500.0,
            places=2,
            msg="Bookings mode must report the confirmed-SO amount, not invoices.",
        )

    # ------------------------------------------------------------------
    # AC-2: calendar window boundary (current vs prior split)
    # ------------------------------------------------------------------

    def test_bookings_calendar_window_boundary(self):
        """Jan-1-this-year SO is current YTD; Dec-31-last-year SO is excluded
        from current and (being outside the prior Jan1->same-day window) also
        excluded from prior. A clearly-in-prior-window SO lands in prior."""
        self.param.set_param(self.param_key, "bookings")
        partner, ou = self._make_company("Calendar Boundary Co")
        today = date.today()

        # In current calendar window (Jan 1 this year .. today)
        self._make_confirmed_order(partner, 300.0, order_date=date(today.year, 1, 1))
        # Just outside current window, below the prior window's start too
        # (prior window = Jan 1 last year .. same day last year), so excluded both.
        self._make_confirmed_order(
            partner, 999.0, order_date=date(today.year - 1, 12, 31)
        )
        # Clearly inside the prior calendar window.
        prior_in_window = today - relativedelta(years=1)
        self._make_confirmed_order(partner, 400.0, order_date=prior_in_window)

        ou.invalidate_recordset()
        self.assertAlmostEqual(
            ou.ytd_sales,
            300.0,
            places=2,
            msg="Only the Jan-1-this-year SO belongs to the current calendar YTD.",
        )
        self.assertAlmostEqual(
            ou.ytd_sales_prior_year,
            400.0,
            places=2,
            msg="Only the in-window prior-year SO belongs to prior calendar YTD; "
            "Dec-31-last-year is excluded.",
        )

    # ------------------------------------------------------------------
    # AC-2 (reuse path): mixed-currency bookings convert via _sum_in_currency
    # ------------------------------------------------------------------

    def test_bookings_mixed_currency_converts(self):
        """Two confirmed SOs in different currencies sum into ytd_sales converted
        to the OU currency (guards reuse of _sum_in_currency, not raw summing)."""
        self.param.set_param(self.param_key, "bookings")
        partner, ou = self._make_company("Bookings FX Co")

        self._make_confirmed_order(partner, 100.0)  # company currency
        self._make_confirmed_order(
            partner, 100.0, currency=self.foreign_currency
        )  # 100 EUR @1.25 = 125

        ou.invalidate_recordset()
        self.assertAlmostEqual(
            ou.ytd_sales,
            225.0,
            places=2,
            msg="100 company-currency + 100 EUR@1.25 must convert to 225, not 200.",
        )

    # ------------------------------------------------------------------
    # AC-1/AC-3: settings round-trip + recompute trigger via the wizard
    # ------------------------------------------------------------------

    def test_settings_form_persists_and_recomputes(self):
        """Saving ytd_metric_basis='bookings' through the res.config.settings
        wizard persists the ir.config_parameter AND leaves ytd_sales reflecting
        bookings afterward (confirms set_values fired the recompute)."""
        partner, ou = self._make_company("Settings RoundTrip Co")
        self._make_posted_invoice(partner, 1000.0)
        self._make_confirmed_order(partner, 4242.0)

        # Default fiscal first.
        ou.invalidate_recordset()
        self.assertAlmostEqual(ou.ytd_sales, 1000.0, places=2)

        # Exercise the real wizard save path (execute() -> set_values()) directly
        # rather than driving the full Settings Form. Other modules installed in
        # the integration stack (e.g. sh_rma) contribute their own conditionally-
        # required fields to res.config.settings, which a full Form().save() would
        # demand we fill even though they are irrelevant to the YTD basis under
        # test. Creating the wizard with only our setting and calling execute()
        # runs the exact persistence + recompute path this test cares about.
        self.env["res.config.settings"].create(
            {"ytd_metric_basis": "bookings"}
        ).execute()

        self.assertEqual(
            self.param.get_param(self.param_key),
            "bookings",
            "Wizard save must persist the ir.config_parameter.",
        )
        ou.invalidate_recordset()
        self.assertAlmostEqual(
            ou.ytd_sales,
            4242.0,
            places=2,
            msg="set_values must recompute stored ytd_sales to the bookings figure.",
        )
