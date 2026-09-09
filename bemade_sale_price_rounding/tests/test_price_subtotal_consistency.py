# -*- coding: utf-8 -*-
"""
Tests for Bug 1 — price_subtotal uses unrounded price_unit.

Acceptance criteria:

A1. Given a sale.order.line whose pricelist computation produces an unrounded
    raw price_unit (e.g. 288.480769), after the line is saved the persisted
    price_unit is rounded to Product Price decimal precision AND price_subtotal
    equals round(price_unit, dp) * product_uom_qty (modulo tax adjustments).
    Tolerance: abs(price_subtotal - round(price_unit, 2) * qty) < 0.01.

A2. A1 holds in state draft (fresh quote), and after action_confirm() (sale).
    Re-triggering pricelist recomputation must not reintroduce the unrounded
    value into price_subtotal.

A3. The PDF quotation/order report sees price_unit × qty == price_subtotal
    consistently — no penny drift on any single line.

A4. Regression test: create a SO with a pricelist that produces a
    non-terminating decimal price_unit. Assert A1 in both draft and after
    action_confirm().
"""
from odoo.fields import Command
from odoo.tests import Form, tagged
from odoo.tools import float_compare

from odoo.addons.sale.tests.common import SaleCommon


@tagged("post_install", "-at_install")
class TestPriceSubtotalConsistency(SaleCommon):
    """Regression tests for Bug 1: price_subtotal must be computed from the
    rounded price_unit, not the raw float returned by pricelist computation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._enable_pricelists()

        # Product whose standard_price produces non-terminating decimal when
        # a formula pricelist is applied. We use 375.024 as the "supplier cost"
        # and a 23.07% discount to get 375.024 * (1 - 0.2307) = 288.480769...
        #
        # Actually we model it with price_discount = 23.07 on a formula rule
        # (base = lst_price), so:
        #   raw = lst_price * (1 - 23.07/100) = 375.024 * 0.7693 = 288.480...
        #
        # Set lst_price to 375.024 to reproduce the irrational value.
        cls.product.lst_price = 375.024
        cls.product.standard_price = 375.024

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_supplierinfo_pricelist(self, name="Supplierinfo Pricelist"):
        """Create a percentage-discount pricelist that yields a non-terminating
        decimal from our product's lst_price (375.024 * (1 - 0.2307) ≈ 288.48).
        """
        pricelist = self.env["product.pricelist"].create({
            "name": name,
            "currency_id": self.env.company.currency_id.id,
            "item_ids": [Command.create({
                "compute_price": "percentage",
                "percent_price": 23.07,
                "applied_on": "3_global",
            })],
        })
        return pricelist

    def _make_so_with_pricelist(self, pricelist):
        """Create a sale order using Form (pricelist set before product line)."""
        with Form(self.env["sale.order"]) as order_form:
            order_form.partner_id = self.partner
            order_form.pricelist_id = pricelist
            with order_form.order_line.new() as line_form:
                line_form.product_id = self.product
        return order_form.record

    def _assert_subtotal_consistent(self, line):
        """Assert price_subtotal == rounded_price_unit * qty within 1 cent."""
        currency = line.currency_id or self.env.company.currency_id
        dp = self.env["decimal.precision"].precision_get("Product Price")
        rounded_unit = currency.round(line.price_unit)
        expected_subtotal = rounded_unit * line.product_uom_qty
        diff = abs(line.price_subtotal - expected_subtotal)
        self.assertLess(
            diff,
            10 ** -dp,
            f"price_subtotal {line.price_subtotal!r} != "
            f"round(price_unit={line.price_unit!r}, {dp}) * "
            f"qty={line.product_uom_qty!r} = {expected_subtotal!r} "
            f"(diff={diff!r})",
        )

    def _assert_price_unit_rounded(self, line):
        """Assert price_unit itself is already rounded to currency precision."""
        currency = line.currency_id or self.env.company.currency_id
        rounded = currency.round(line.price_unit)
        self.assertEqual(
            line.price_unit,
            rounded,
            f"price_unit {line.price_unit!r} is not rounded; expected {rounded!r}",
        )

    # ------------------------------------------------------------------
    # A1 / A4 — draft state
    # ------------------------------------------------------------------

    def test_price_subtotal_equals_rounded_unit_times_qty_draft(self):
        """A1/A4 (draft): price_subtotal uses the rounded price_unit, not the
        raw float from the pricelist percentage rule.

        375.024 * (1 - 0.2307) = 288.480...  — non-terminating.
        After rounding: price_unit = 288.48 (2 dp).
        price_subtotal must equal 288.48 * qty.
        """
        pricelist = self._make_supplierinfo_pricelist()
        order = self._make_so_with_pricelist(pricelist)
        line = order.order_line[:1]

        # Verify the raw computation would be non-round
        raw = 375.024 * (1 - 23.07 / 100)
        dp = self.env["decimal.precision"].precision_get("Product Price")
        self.assertNotEqual(
            raw,
            round(raw, dp),
            "Test setup error: choose values that produce irrational decimals",
        )

        self._assert_price_unit_rounded(line)
        self._assert_subtotal_consistent(line)

    # ------------------------------------------------------------------
    # A2 — sale state (after action_confirm)
    # ------------------------------------------------------------------

    def test_price_subtotal_consistent_after_action_confirm(self):
        """A2/A4 (sale state): price_subtotal is still consistent with the
        rounded price_unit after the SO is confirmed.
        """
        pricelist = self._make_supplierinfo_pricelist()
        order = self._make_so_with_pricelist(pricelist)
        line = order.order_line[:1]

        order.action_confirm()
        line.invalidate_recordset()

        self._assert_price_unit_rounded(line)
        self._assert_subtotal_consistent(line)

    # ------------------------------------------------------------------
    # A2 — qty change recomputes cleanly
    # ------------------------------------------------------------------

    def test_price_subtotal_after_qty_change_recomputes_cleanly(self):
        """A2: changing product_uom_qty recomputes price_subtotal from the
        rounded price_unit, not the raw float.
        """
        pricelist = self._make_supplierinfo_pricelist()
        order = self._make_so_with_pricelist(pricelist)
        line = order.order_line[:1]

        # Verify initial state
        self._assert_price_unit_rounded(line)
        self._assert_subtotal_consistent(line)

        # Change qty and re-assert
        with Form(order) as order_form:
            with order_form.order_line.edit(0) as line_form:
                line_form.product_uom_qty = 3.0
        line = order.order_line[:1]

        self._assert_price_unit_rounded(line)
        self._assert_subtotal_consistent(line)

    # ------------------------------------------------------------------
    # A2 — pricelist change recomputes cleanly
    # ------------------------------------------------------------------

    def test_price_subtotal_after_pricelist_change(self):
        """A2: swapping the pricelist triggers a fresh _reset_price_unit, and
        the resulting price_subtotal is still consistent with the rounded
        price_unit.
        """
        pricelist1 = self._make_supplierinfo_pricelist("Pricelist 23.07%")
        pricelist2 = self.env["product.pricelist"].create({
            "name": "Pricelist 10.03%",
            "currency_id": self.env.company.currency_id.id,
            "item_ids": [Command.create({
                "compute_price": "percentage",
                "percent_price": 10.03,
                "applied_on": "3_global",
            })],
        })

        order = self._make_so_with_pricelist(pricelist1)
        line = order.order_line[:1]

        self._assert_price_unit_rounded(line)
        self._assert_subtotal_consistent(line)

        # Swap pricelist
        with Form(order) as order_form:
            order_form.pricelist_id = pricelist2
        line = order.order_line[:1]

        self._assert_price_unit_rounded(line)
        self._assert_subtotal_consistent(line)
