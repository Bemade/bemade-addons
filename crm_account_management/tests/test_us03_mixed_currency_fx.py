# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""
US-03: Bookings totals convert mixed-currency orders to the OU currency.

Acceptance criteria
-------------------
1. Booking totals convert each won order's amount to a common currency
   (OU currency_id) before summing when sources are mixed.  No more raw
   numeric summing of, e.g., USD + CAD into a CAD-only field.
2. Single-currency accounts are unaffected (no regression from _convert
   same-currency short-circuit).
3. Open-orders path (open_orders_amount) uses the same conversion helper.
4. The YTD/rolling metrics ALSO convert mixed currencies before summing:
   ytd_sales (invoice-based on the default 'fiscal' basis) converts each
   account.move from its own currency — amount_total is in the invoice's own
   currency, not the company currency; rolling_12m_sales (bookings-based)
   converts each confirmed sale.order from its own currency.
5. The "To Invoice" metric subtracts invoiced amounts in the converted
   space without double-converting (invoiced is in the invoice currency,
   not the order currency).
6. The sales-by-period chart converts each currency bucket before summing
   into a period total.
"""
from datetime import date

from odoo.tests import tagged

from odoo.addons.crm_account_management.tests.common import OUTestCommon


@tagged("post_install", "-at_install")
class TestUS03MixedCurrencyFX(OUTestCommon):
    """
    US-03: Mixed-currency FX conversion for OU bookings / order metrics.

    Each test uses a known FX rate so expected values can be computed exactly.
    The company currency (whatever AccountTestInvoicingCommon sets up, typically
    USD) is used as the OU's ``currency_id``; a second currency (EUR) is set up
    with a well-known rate so assertions are deterministic.

    Rate setup: 1 EUR = 1.25 company-currency units.
    The ``rate`` field on ``res.currency.rate`` stores "units of this currency
    per 1 unit of company currency", so ``rate = 1 / 1.25 = 0.8``.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]

        # Create a test product used across all tests
        cls.product = cls.env["product.product"].create(
            {
                "name": "FX Test Product",
                "list_price": 100.0,
            }
        )

        # Set up a foreign currency: 1 EUR = 1.25 company-currency units.
        # rate = 0.8 means 0.8 EUR per 1 unit of company currency, so
        # inverse_rate = 1/0.8 = 1.25: 1 EUR converts to 1.25 company-currency.
        cls.foreign_currency = cls.setup_other_currency(
            "EUR",
            rates=[
                ("2000-01-01", 0.8),
            ],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_company(self, name):
        """Create a top-level company partner (triggers OU auto-create)."""
        partner = self.partner_model.create({"name": name, "is_company": True})
        ou = self.ou_model.search([("owner_id", "=", partner.id)], limit=1)
        return partner, ou

    def _make_confirmed_order(self, partner, amount, currency=None, order_date=None):
        """Create and confirm a sale.order with a single line of the given amount.

        In Odoo 18, sale.order.currency_id is a stored computed field driven by the
        pricelist (``pricelist_id.currency_id``), so the currency cannot be set
        directly on the order.  When a non-default currency is requested, a throwaway
        pricelist in that currency is created and attached to the order so that
        ``_compute_currency_id`` picks it up correctly.
        """
        if order_date is None:
            order_date = date.today()
        vals = {
            "partner_id": partner.id,
            "date_order": order_date,
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
            # In Odoo 18, sale.order.currency_id is computed from the pricelist.
            # Create a pricelist in the requested currency so the order adopts it.
            pricelist = self.env["product.pricelist"].create({
                "name": f"Test pricelist {currency.name}",
                "currency_id": currency.id,
            })
            vals["pricelist_id"] = pricelist.id
        order = self.env["sale.order"].create(vals)
        order.action_confirm()
        return order

    def _make_posted_invoice(self, partner, amount, currency=None, invoice_date=None):
        """Create and post a customer invoice of the given amount/currency."""
        if invoice_date is None:
            invoice_date = date.today()
        vals = {
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
        if currency:
            vals["currency_id"] = currency.id
        invoice = self.env["account.move"].create(vals)
        invoice.action_post()
        return invoice

    # ------------------------------------------------------------------
    # Test 1: Mixed-currency won orders convert before summing
    # ------------------------------------------------------------------

    def test_won_quotations_amount_converts_mixed_currency(self):
        """
        AC-1: won_quotations_amount converts each order to the OU currency.

        One order is in the company currency (100 units) and one is in EUR
        (100 EUR).  With 1 EUR = 1.25 company-currency, the converted total
        must equal 100 + 125 = 225, NOT the raw numeric sum of 200.
        """
        partner, ou = self._make_company("FX Test Partner 1")

        # Order in company currency
        self._make_confirmed_order(partner, 100.0)
        # Order in EUR (100 EUR × 1.25 = 125 company-currency)
        self._make_confirmed_order(partner, 100.0, currency=self.foreign_currency)

        ou.invalidate_recordset()
        # Raw numeric sum would be 200; correctly converted total is 225.
        self.assertGreater(
            ou.won_quotations_amount,
            200.0,
            "Mixed-currency bookings must be converted before summing, not added numerically.",
        )
        self.assertAlmostEqual(
            ou.won_quotations_amount,
            225.0,
            places=2,
            msg="100 company-currency + 100 EUR@1.25 must equal 225 company-currency.",
        )

    # ------------------------------------------------------------------
    # Test 2: Single-currency total is unchanged
    # ------------------------------------------------------------------

    def test_single_currency_total_unchanged(self):
        """
        AC-2: When all orders share the OU currency, the total equals the raw sum.

        _convert short-circuits to identity when source == target, so no
        rounding or rate-table errors are introduced for single-currency accounts.
        """
        partner, ou = self._make_company("FX Test Partner 2")

        self._make_confirmed_order(partner, 100.0)
        self._make_confirmed_order(partner, 100.0)

        ou.invalidate_recordset()
        self.assertAlmostEqual(
            ou.won_quotations_amount,
            200.0,
            places=2,
            msg="Single-currency bookings must equal the exact sum without rounding deviation.",
        )

    # ------------------------------------------------------------------
    # Test 3: Open orders path also converts
    # ------------------------------------------------------------------

    def test_open_orders_amount_converts_mixed_currency(self):
        """
        AC-3: open_orders_amount converts each open order to the OU currency.

        One open order in company currency (100) and one in EUR (100 EUR),
        both not invoiced.  The reported amount must equal 225, not 200.
        """
        partner, ou = self._make_company("FX Test Partner 3")

        # Confirmed but not invoiced → open orders
        self._make_confirmed_order(partner, 100.0)
        self._make_confirmed_order(partner, 100.0, currency=self.foreign_currency)

        ou.invalidate_recordset()
        self.assertGreater(
            ou.open_orders_amount,
            200.0,
            "Mixed-currency open orders must be converted before summing.",
        )
        self.assertAlmostEqual(
            ou.open_orders_amount,
            225.0,
            places=2,
            msg="100 company-currency + 100 EUR@1.25 must equal 225 in open_orders_amount.",
        )

    # ------------------------------------------------------------------
    # Test 4: YTD sales (invoice-based) converts mixed currency
    # ------------------------------------------------------------------

    def test_ytd_sales_converts_mixed_currency(self):
        """
        AC-4: ytd_sales converts each posted invoice to the OU currency.

        account.move.amount_total is in the invoice's own currency, so a
        company-currency invoice (100) plus a EUR invoice (100 EUR @ 1.25 = 125)
        must total 225 in ytd_sales, NOT the naive numeric sum of 200.

        This guards the invoice path that the original #124 fix left summing
        raw amount_total across currencies.
        """
        partner, ou = self._make_company("FX Test Partner 4")

        self._make_posted_invoice(partner, 100.0)
        self._make_posted_invoice(partner, 100.0, currency=self.foreign_currency)

        ou.invalidate_recordset()
        self.assertGreater(
            ou.ytd_sales,
            200.0,
            "Mixed-currency invoices must be FX-converted before summing into ytd_sales.",
        )
        self.assertAlmostEqual(
            ou.ytd_sales,
            225.0,
            places=2,
            msg="100 company-currency + 100 EUR@1.25 must equal 225 in ytd_sales.",
        )

    # ------------------------------------------------------------------
    # Test 5: Rolling 12M sales converts mixed currency
    # ------------------------------------------------------------------

    def test_rolling_12m_sales_converts_mixed_currency(self):
        """
        AC-4: rolling_12m_sales converts each mixed-currency booking before
        summing.

        rolling_12m_sales is a bookings metric: it aggregates confirmed
        sale.orders (state='sale') over the trailing 12 months via
        _sum_in_currency, which converts each order from its own currency at
        its date_order.  A company-currency order (100) plus a EUR order
        (100 EUR @ 1.25 = 125) must total 225, not the naive numeric sum of 200.
        """
        partner, ou = self._make_company("FX Test Partner 5")

        # date.today() is inside the rolling-12m window (> today-12mo, <= today).
        self._make_confirmed_order(partner, 100.0)
        self._make_confirmed_order(partner, 100.0, currency=self.foreign_currency)

        ou.invalidate_recordset()
        self.assertAlmostEqual(
            ou.rolling_12m_sales,
            225.0,
            places=2,
            msg="100 company-currency + 100 EUR@1.25 must equal 225 in rolling_12m_sales.",
        )

    # ------------------------------------------------------------------
    # Test 6: To-Invoice does not double-convert the invoiced amount
    # ------------------------------------------------------------------

    def test_to_invoice_no_double_conversion(self):
        """
        AC-5: open_orders_to_invoice_amount subtracts the invoiced amount in
        the converted space without double-converting.

        A single EUR order of 100 EUR (= 125 company-currency) is partially
        invoiced for 40 EUR (= 50 company-currency).  The remaining amount to
        invoice must be 125 - 50 = 75 company-currency.

        The old code converted the per-invoice amount_total (already in the
        invoice/EUR currency) a second time *as if* it were the order currency,
        which for a EUR order/EUR invoice happened to be a no-op — but it summed
        invoices that may be in another currency wrongly.  Routing the invoiced
        amount through the same per-invoice converter keeps it correct and
        single-converted.
        """
        partner, ou = self._make_company("FX Test Partner 6")

        order = self._make_confirmed_order(
            partner, 100.0, currency=self.foreign_currency
        )
        # Partially invoice: post an invoice for 40 EUR against this order's partner.
        # (open_orders_to_invoice_amount nets posted invoices on the order.)
        invoice = order._create_invoices()
        # Reduce the invoiced quantity/amount to a partial 40 EUR.
        invoice.invoice_line_ids[0].price_unit = 40.0
        invoice.action_post()

        ou.invalidate_recordset()
        # 125 (order in company-currency) - 50 (40 EUR invoiced @1.25) = 75.
        self.assertAlmostEqual(
            ou.open_orders_to_invoice_amount,
            75.0,
            places=2,
            msg="To-Invoice must net the converted invoiced amount: 125 - 50 = 75.",
        )

    # ------------------------------------------------------------------
    # Test 7: sales-by-period chart converts each currency bucket
    # ------------------------------------------------------------------

    def test_sales_by_period_converts_mixed_currency(self):
        """
        AC-6: get_sales_by_period converts each currency bucket before summing
        into a period total.

        Two invoices in the same period (this month), one company-currency (100)
        and one EUR (100 EUR @ 1.25 = 125), must roll up to 225 for that period,
        not the naive SQL sum of 200.
        """
        partner, ou = self._make_company("FX Test Partner 7")

        self._make_posted_invoice(partner, 100.0)
        self._make_posted_invoice(partner, 100.0, currency=self.foreign_currency)

        data = ou.get_sales_by_period(period="month", periods=1)
        total = sum(row["total"] or 0.0 for row in data)
        self.assertAlmostEqual(
            total,
            225.0,
            places=2,
            msg="Mixed-currency invoices in one period must convert to 225, not sum to 200.",
        )
