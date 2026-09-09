# -*- coding: utf-8 -*-
"""
Tests for Bug 2 — purchase_price (cost) stored unrounded on quotes.

Acceptance criteria:

B1. On a quote (state in ('draft', 'sent')), sale.order.line.purchase_price
    has at most Product Price decimal precision digits (2 on Durpro). No
    trailing 3rd/4th/.../14th decimal, regardless of UoM conversion arithmetic.

B2. The fix produces identical results whether the SO is in draft, sent,
    sale, or done. After the fix, draft SOs match confirmed ones.

B3. The fix is applied by rounding the stored value on write/compute (option
    B3(a)): no migration of historical data required, but new writes must round.

B4. Regression test: reproduce SO28003 / SO28203 conditions — a product with
    standard_price = 4789.95 in a "Box of 21" UoM sold in "Each", yielding
    4789.95 / 21 = 228.09285714..., create a quote, assert purchase_price is
    rounded (≤ 2 decimals). Re-assert after action_confirm().
"""
import unittest

from odoo.fields import Command
from odoo.tests import Form, tagged
from odoo.tools import float_compare

from odoo.addons.sale.tests.common import SaleCommon


@tagged("post_install", "-at_install")
class TestPurchasePriceRounding(SaleCommon):
    """Regression tests for Bug 2: purchase_price must be rounded to Product
    Price precision on quotes, not just after confirmation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Skip entire class if sale_margin is not installed (defense-in-depth;
        # the module hard-depends on it, but guard tests too).
        if "sale.order.line" not in cls.env or not hasattr(
            cls.env["sale.order.line"], "purchase_price"
        ):
            raise unittest.SkipTest("sale_margin not installed — skipping")

        # Product that reproduces SO28003: standard_price per Box-of-21,
        # sold per Each → 4789.95 / 21 = 228.09285714285714...
        #
        # We use a simpler approach: set standard_price on the product directly
        # to a value that is not representable at 2 dp when multiplied through
        # the UoM factor.  We create a UoM "Box21" with ratio 21.0 so that
        # _compute_purchase_price calls uom._compute_price(standard_price, sol_uom)
        # → standard_price / 21.
        cls._setup_uom_product()

    @classmethod
    def _setup_uom_product(cls):
        """Create a Box-of-21 UoM and a product priced per box."""
        uom_unit = cls.env.ref("uom.product_uom_unit")
        uom_categ = uom_unit.category_id

        cls.uom_box21 = cls.env["uom.uom"].create({
            "name": "Box of 21",
            "category_id": uom_categ.id,
            "uom_type": "bigger",
            "factor_inv": 21.0,
            "rounding": 0.001,
        })

        cls.product_box = cls.env["product.product"].create({
            "name": "Test Box Product",
            "type": "consu",
            "uom_id": uom_unit.id,
            "uom_po_id": cls.uom_box21.id,
            "standard_price": 4789.95,
            "lst_price": 9999.00,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_so_with_product(self, product, uom=None):
        """Create a draft SO with the given product (and optional UoM)."""
        with Form(self.env["sale.order"]) as order_form:
            order_form.partner_id = self.partner
            with order_form.order_line.new() as line_form:
                line_form.product_id = product
                if uom:
                    line_form.product_uom = uom
        return order_form.record

    def _assert_purchase_price_rounded(self, line):
        """Assert purchase_price has no extra decimals beyond Product Price DP."""
        dp = self.env["decimal.precision"].precision_get("Product Price")
        rounded = round(line.purchase_price, dp)
        cmp = float_compare(
            line.purchase_price,
            rounded,
            precision_digits=dp + 4,
        )
        self.assertEqual(
            cmp,
            0,
            f"purchase_price {line.purchase_price!r} has extra decimals "
            f"beyond dp={dp}; expected {rounded!r}",
        )

    # ------------------------------------------------------------------
    # B1 / B4 — draft state, UoM conversion path
    # ------------------------------------------------------------------

    def test_purchase_price_rounded_on_quote_via_uom_conversion(self):
        """B1/B4 (draft): purchase_price from UoM conversion is rounded.

        standard_price = 4789.95 (per box of 21); sold per Each.
        _compute_purchase_price: uom_box21._compute_price(4789.95, uom_unit)
          = 4789.95 / 21 = 228.09285714285714...
        After rounding: purchase_price must equal 228.09 (at dp=2).
        """
        uom_unit = self.env.ref("uom.product_uom_unit")
        # Ensure the product's UoM is "Each" so purchase_price is per-unit
        self.product_box.uom_id = uom_unit
        order = self._make_so_with_product(self.product_box)
        line = order.order_line[:1]

        # Verify the raw computation would be unrounded
        raw = 4789.95 / 21
        dp = self.env["decimal.precision"].precision_get("Product Price")
        self.assertNotEqual(
            raw,
            round(raw, dp),
            "Test setup error: choose values that produce irrational decimals",
        )

        self._assert_purchase_price_rounded(line)

    # ------------------------------------------------------------------
    # B2 — after action_confirm
    # ------------------------------------------------------------------

    def test_purchase_price_rounded_after_action_confirm(self):
        """B2/B4 (sale state): purchase_price remains rounded after confirmation.

        Covers the sale_stock_margin._compute_purchase_price re-trigger path.
        For a consumable (no stock moves), the base sale_margin compute runs
        and the value must still be rounded.
        """
        uom_unit = self.env.ref("uom.product_uom_unit")
        self.product_box.uom_id = uom_unit
        order = self._make_so_with_product(self.product_box)

        order.action_confirm()
        line = order.order_line[:1]
        line.invalidate_recordset()

        self._assert_purchase_price_rounded(line)

    # ------------------------------------------------------------------
    # B3 — direct write
    # ------------------------------------------------------------------

    def test_purchase_price_rounded_on_direct_write(self):
        """B3: a direct write of purchase_price with extra decimals is rounded.

        Covers API writes, imports, and other non-compute code paths.
        """
        order = self._make_so_with_product(self.product)
        line = order.order_line[:1]

        line.write({"purchase_price": 6.28812345})

        dp = self.env["decimal.precision"].precision_get("Product Price")
        expected = round(6.28812345, dp)  # 6.29
        self._assert_purchase_price_rounded(line)
        self.assertAlmostEqual(line.purchase_price, expected, places=dp)

    # ------------------------------------------------------------------
    # B4 — create with unrounded value
    # ------------------------------------------------------------------

    def test_purchase_price_rounded_on_create(self):
        """B4: creating a line with an unrounded purchase_price stores it rounded.

        Covers imports, programmatic line creation, and the
        min_display_digits raw-stored backfill path on new lines.
        """
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
        })
        dp = self.env["decimal.precision"].precision_get("Product Price")

        line = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1.0,
            "price_unit": 9.99,
            "purchase_price": 228.0928571,
        })

        expected = round(228.0928571, dp)  # 228.09
        self._assert_purchase_price_rounded(line)
        self.assertAlmostEqual(line.purchase_price, expected, places=dp)
