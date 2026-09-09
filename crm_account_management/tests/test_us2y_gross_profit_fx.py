# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""
US-2Y: Gross-profit margin converts revenue and cost to a common currency.

Acceptance criteria
-------------------
1. For a foreign-currency-billed invoice, the per-invoice gross margin is
   computed with revenue and cost in a common currency: revenue
   (``price_subtotal``, in the invoice currency) is converted to company
   currency at the invoice date, while cost (``standard_price``) is already in
   company currency and needs no conversion. No more differencing a
   foreign-currency revenue against a company-currency cost, which manufactures
   fake margins equal to ~the FX rate.
2. Single-currency invoices (invoice currency == company currency) are
   unaffected: the conversion short-circuits to identity, so the margin equals
   the plain (revenue - cost) / revenue.
3. A foreign-currency invoice that is genuinely a loss still reads as a loss
   (the fix must not paper over real negative margins).
"""
from datetime import date

from odoo.tests import tagged

from odoo.addons.crm_account_management.tests.common import OUTestCommon


@tagged("post_install", "-at_install")
class TestUS2YGrossProfitFX(OUTestCommon):
    """
    Gross-profit FX conversion for the avg_gross_profit_percentage compute.

    Rate setup: 1 EUR = 1.25 company-currency units.
    ``res.currency.rate`` stores "units of this currency per 1 unit of company
    currency", so rate = 1 / 1.25 = 0.8.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]

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
        partner = self.partner_model.create({"name": name, "is_company": True})
        ou = self.ou_model.search([("owner_id", "=", partner.id)], limit=1)
        return partner, ou

    def _make_product(self, standard_price):
        return self.env["product.product"].create(
            {
                "name": "GP FX Product",
                "list_price": standard_price * 2,
                "standard_price": standard_price,  # company currency
            }
        )

    def _make_posted_invoice(self, partner, product, qty, price_unit, currency=None):
        vals = {
            "partner_id": partner.id,
            "move_type": "out_invoice",
            "invoice_date": date.today(),
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "quantity": qty,
                        "price_unit": price_unit,
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
    # Test 1: foreign-currency invoice margin converts both sides
    # ------------------------------------------------------------------

    def test_gross_profit_converts_foreign_currency_invoice(self):
        """
        AC-1: A EUR-billed invoice must convert revenue and cost to a common
        currency before differencing.

        Product cost (standard_price) = 100 company-currency.
        Invoice: 1 unit @ 100 EUR -> price_subtotal = 100 EUR.
        Converted revenue = 100 EUR * 1.25 = 125 company-currency.
        Cost = 1 * 100 = 100 company-currency.
        Correct margin = (125 - 100) / 125 = 0.20.

        The BUGGY code differences the EUR revenue number (100) against the
        company-currency cost (100): (100 - 100) / 100 = 0.0 -- a fake zero
        margin manufactured purely by the FX rate.
        """
        partner, ou = self._make_company("GP FX Partner 1")
        product = self._make_product(standard_price=100.0)

        self._make_posted_invoice(
            partner, product, qty=1, price_unit=100.0, currency=self.foreign_currency
        )

        ou.invalidate_recordset()
        self.assertAlmostEqual(
            ou.avg_gross_profit_percentage,
            0.20,
            places=2,
            msg=(
                "EUR-billed invoice margin must convert revenue and cost to a "
                "common currency: (125 - 100) / 125 = 0.20, not the raw "
                "(100 - 100) / 100 = 0.0."
            ),
        )

    # ------------------------------------------------------------------
    # Test 2: single-currency invoice unaffected
    # ------------------------------------------------------------------

    def test_gross_profit_single_currency_unchanged(self):
        """
        AC-2: A company-currency invoice margin equals the plain ratio.

        Product cost = 60; invoice 1 unit @ 100 company-currency.
        Margin = (100 - 60) / 100 = 0.40, with no FX deviation.
        """
        partner, ou = self._make_company("GP FX Partner 2")
        product = self._make_product(standard_price=60.0)

        self._make_posted_invoice(partner, product, qty=1, price_unit=100.0)

        ou.invalidate_recordset()
        self.assertAlmostEqual(
            ou.avg_gross_profit_percentage,
            0.40,
            places=2,
            msg="Single-currency invoice must yield (100 - 60) / 100 = 0.40.",
        )

    # ------------------------------------------------------------------
    # Test 3: a genuine foreign-currency loss still reads as a loss
    # ------------------------------------------------------------------

    def test_gross_profit_real_foreign_loss_preserved(self):
        """
        AC-3: The conversion must not hide a real negative margin.

        Product cost = 200 company-currency.
        Invoice: 1 unit @ 100 EUR -> converted revenue = 125 company-currency.
        Cost = 200 company-currency.
        Margin = (125 - 200) / 125 = -0.60 -- a genuine loss, still negative.
        """
        partner, ou = self._make_company("GP FX Partner 3")
        product = self._make_product(standard_price=200.0)

        self._make_posted_invoice(
            partner, product, qty=1, price_unit=100.0, currency=self.foreign_currency
        )

        ou.invalidate_recordset()
        self.assertAlmostEqual(
            ou.avg_gross_profit_percentage,
            -0.60,
            places=2,
            msg="A genuine foreign-currency loss must remain negative: "
            "(125 - 200) / 125 = -0.60.",
        )
