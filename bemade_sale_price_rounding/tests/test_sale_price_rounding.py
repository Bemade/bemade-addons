# -*- coding: utf-8 -*-
"""
Tests for bemade_sale_price_rounding

Acceptance criteria:

1. Percentage pricelist rule: price_unit must be rounded to currency precision.
   E.g. $9.99 at 33% off → 6.69, not 6.6933.

2. Formula pricelist rule (cost + markup): same rounding guarantee.

3. Multi-step pricelist chain (realistic Durpro scenario): supplier cost →
   base pricelist (+35% markup) → public pricelist (+42% markup) produces
   irrational intermediate values that must be rounded on the SO line.

4. Fixed pricelist price: already exact, must remain exact.

5. Manual price override: a user-typed price_unit must not be altered by
   this module (only pricelist-computed prices are touched).

6. Multi-currency: rounding uses the *order* currency's precision.

IMPORTANT — use Form to set pricelist BEFORE adding the SO line:
   The pricelist must be set on the order before product lines are added so
   that _reset_price_unit() can see the pricelist and apply the correct rule.
"""
from odoo.fields import Command
from odoo.tests import Form, tagged

from odoo.addons.sale.tests.common import SaleCommon


@tagged("post_install", "-at_install")
class TestSalePriceRounding(SaleCommon):
    """Comprehensive tests verifying price_unit rounding to currency precision."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._enable_pricelists()

        # Product with a price that produces non-round values under most rules.
        # 87.50 * 1.35 = 118.125   (not round)
        # 87.50 * 1.35 * 1.42 = 167.7375  (not round)
        # These deliberately irrational results stress-test our rounding.
        cls.product.lst_price = 87.50
        cls.product.standard_price = 87.50

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_pricelist(self, name, currency=None, items=None):
        """Create a pricelist with optional rule items."""
        vals = {
            "name": name,
            "currency_id": (currency or self.env.company.currency_id).id,
        }
        if items:
            vals["item_ids"] = [Command.create(i) for i in items]
        return self.env["product.pricelist"].create(vals)

    def _make_so_with_pricelist(self, pricelist):
        """Create a sale order with pricelist set BEFORE adding the product line.

        This simulates the real user flow: open SO form → set pricelist →
        add product. Without this ordering, _reset_price_unit() may not see
        the pricelist rule and defaults to lst_price (already 2 decimals).
        """
        with Form(self.env["sale.order"]) as order_form:
            order_form.partner_id = self.partner
            order_form.pricelist_id = pricelist
            with order_form.order_line.new() as line_form:
                line_form.product_id = self.product
        return order_form.record

    def _assert_price_rounded(self, line):
        """Assert price_unit equals its currency-rounded value (exact equality)."""
        currency = line.currency_id or self.env.company.currency_id
        rounded = currency.round(line.price_unit)
        self.assertEqual(
            line.price_unit,
            rounded,
            f"price_unit {line.price_unit!r} is not rounded to currency precision "
            f"({currency.name}, rounding={currency.rounding}); "
            f"expected {rounded!r}",
        )

    # ------------------------------------------------------------------
    # Test cases
    # ------------------------------------------------------------------

    def test_pricelist_chain_rounds_price_unit(self):
        """Multi-step pricelist chain produces a rounded price_unit.

        Mimics the real Durpro scenario:
          - base_pricelist: standard_price × 1.35  →  87.50 × 1.35 = 118.125
          - public_pricelist (based on base): × 1.42  →  118.125 × 1.42 = 167.7375

        Without the fix, 167.7375 (or a similar irrational float) ends up
        stored on the SO line.  With the fix it must be 167.74.
        """
        base_pricelist = self._make_pricelist(
            "Base Cost +35%",
            items=[{
                "compute_price": "formula",
                "base": "standard_price",
                "price_discount": -35,   # negative = markup: cost * (1 - (-0.35)) = cost * 1.35
                "applied_on": "3_global",
            }],
        )
        public_pricelist = self._make_pricelist(
            "Public +42% on base",
            items=[{
                "compute_price": "formula",
                "base": "pricelist",
                "base_pricelist_id": base_pricelist.id,
                "price_discount": -42,   # base * 1.42
                "applied_on": "3_global",
            }],
        )

        order = self._make_so_with_pricelist(public_pricelist)
        line = order.order_line[:1]

        # Verify the raw math would be non-round
        raw = 87.50 * 1.35 * 1.42
        self.assertNotEqual(raw, round(raw, 2),
                            "Test setup error: choose numbers that produce irrational values")

        self._assert_price_rounded(line)

    def test_percentage_pricelist_rounds(self):
        """Single percentage rule: price_unit is rounded to currency precision.

        87.50 * (1 - 0.33) = 58.625  → should be 58.63 (or 58.62 depending
        on rounding direction), but never 58.625.
        """
        pricelist = self._make_pricelist(
            "33% Discount",
            items=[{
                "compute_price": "percentage",
                "percent_price": 33,
                "applied_on": "3_global",
            }],
        )
        order = self._make_so_with_pricelist(pricelist)
        line = order.order_line[:1]
        self._assert_price_rounded(line)

    def test_formula_pricelist_rounds(self):
        """Formula rule based on cost: price_unit is rounded to currency precision.

        standard_price = 87.50, markup -30 (= ×1.30) → 87.50 × 1.30 = 113.75
        That's already round, so we add a markup that isn't:
        standard_price = 77.77, markup -30 → 77.77 × 1.30 = 101.101
        """
        self.product.standard_price = 77.77
        pricelist = self._make_pricelist(
            "Cost +30%",
            items=[{
                "compute_price": "formula",
                "base": "standard_price",
                "price_discount": -30,
                "applied_on": "3_global",
            }],
        )
        order = self._make_so_with_pricelist(pricelist)
        line = order.order_line[:1]

        raw = 77.77 * 1.30
        self.assertNotEqual(raw, round(raw, 2),
                            "Test setup error: use numbers that produce irrational values")
        self._assert_price_rounded(line)

    def test_fixed_price_unaffected(self):
        """A fixed pricelist price produces an exact price_unit, and our rounding
        does not alter it in any unexpected way."""
        pricelist = self._make_pricelist(
            "Fixed $15.00",
            items=[{
                "compute_price": "fixed",
                "fixed_price": 15.00,
                "applied_on": "3_global",
            }],
        )
        order = self._make_so_with_pricelist(pricelist)
        line = order.order_line[:1]
        self._assert_price_rounded(line)
        self.assertEqual(line.price_unit, 15.00)

    def test_pricelist_set_before_line_required(self):
        """Demonstrate correct vs incorrect workflow for pricelist + SO line.

        CORRECT workflow: set pricelist on the order BEFORE adding the product
        line → _reset_price_unit() runs with pricelist context → price gets
        rounded.

        We also verify that once the pricelist IS set first, the irrational
        value from the pricelist chain does not appear on the line.
        """
        base_pricelist = self._make_pricelist(
            "Workflow test - base +35%",
            items=[{
                "compute_price": "formula",
                "base": "standard_price",
                "price_discount": -35,
                "applied_on": "3_global",
            }],
        )

        # CORRECT workflow: pricelist set before line
        with Form(self.env["sale.order"]) as order_form:
            order_form.partner_id = self.partner
            order_form.pricelist_id = base_pricelist  # set FIRST
            with order_form.order_line.new() as line_form:
                line_form.product_id = self.product
        order = order_form.record
        line = order.order_line[:1]

        # price must be rounded
        self._assert_price_rounded(line)

    def test_multicurrency_uses_order_currency_rounding(self):
        """Rounding uses the order currency's precision, not the company currency.

        We create a EUR pricelist with a percentage rule on our non-round
        product price.  The SO line must be rounded to EUR's precision (0.01).
        """
        eur = self.env.ref("base.EUR")
        # Make sure EUR has a rate so conversion doesn't fail
        if not self.env["res.currency.rate"].search(
            [("currency_id", "=", eur.id), ("company_id", "=", self.env.company.id)]
        ):
            self.env["res.currency.rate"].create({
                "currency_id": eur.id,
                "rate": 1.35,
                "company_id": self.env.company.id,
            })

        eur_pricelist = self._make_pricelist(
            "EUR 33% Discount",
            currency=eur,
            items=[{
                "compute_price": "percentage",
                "percent_price": 33,
                "applied_on": "3_global",
            }],
        )
        order = self._make_so_with_pricelist(eur_pricelist)
        line = order.order_line[:1]

        self.assertEqual(line.currency_id, eur,
                         "Order line currency should be EUR")
        self._assert_price_rounded(line)

    def test_direct_write_of_price_unit_is_rounded(self):
        """A direct write of price_unit with extra decimals must be rounded.

        Reproduces the Durpro production bug (IBS Tuboquip / HF 40-40E):
        in Odoo 18 ``sale.order.line.price_unit`` is declared with
        ``min_display_digits='Product Price'`` (no ``digits``), so the Float
        column stores values at full FLOAT8 precision — no automatic rounding
        on write.  The form view formats display via ``min_display_digits``
        (looks fine), but the printed PDF uses a code path that surfaces the
        full stored precision (6+ decimals).

        Our existing ``_get_display_price_ignore_combo`` /
        ``_reset_price_unit`` overrides only run on the compute path.  Any
        other code path that writes ``price_unit`` directly (e.g. a
        downstream module, an import, an API call) leaves an unrounded float
        in the DB.  This test asserts that *any* write to price_unit ends
        up rounded to currency precision.
        """
        # Plain pricelist so the order has a known currency
        pricelist = self._make_pricelist("Plain pricelist for direct-write test")
        order = self._make_so_with_pricelist(pricelist)
        line = order.order_line[:1]

        # Simulate a non-compute code path writing an unrounded float
        line.price_unit = 6.100121999999999
        # The assertion below mirrors the production bug: stored value
        # leaks 6+ decimals onto the printed PDF.
        self._assert_price_rounded(line)
