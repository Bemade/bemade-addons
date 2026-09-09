# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""
US-2Z: All-OU revenue-weighted average gross-profit % comparison figure.

Acceptance criteria
-------------------
1. ``all_ou_avg_gross_profit_percentage`` is the revenue-weighted average GP%
   across ALL organizational units' YTD posted customer invoices:
   ``sum(revenue - cost) / sum(revenue)``. It reuses the same invoice domain
   and per-invoice revenue/cost derivation as the per-OU
   ``avg_gross_profit_percentage`` compute, so the two metrics stay
   consistent.
2. The figure is a single rolled-up number: the SAME value on every OU record.
3. It is revenue-weighted, not a plain mean of per-OU percentages -- so with
   OUs of differing revenue it differs from the simple average of their
   individual GP percentages.
4. Divide-by-zero is guarded: with no qualifying revenue the field is 0.0.
"""
from datetime import date

from odoo.tests import tagged

from odoo.addons.crm_account_management.tests.common import OUTestCommon


@tagged("post_install", "-at_install")
class TestUS2ZAllOUGrossProfit(OUTestCommon):
    """Revenue-weighted all-OU GP% comparison figure."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_company(self, name):
        """Create a company partner; its OU is auto-created by res.partner."""
        partner = self.partner_model.create({"name": name, "is_company": True})
        ou = self.ou_model.search([("owner_id", "=", partner.id)], limit=1)
        self.assertTrue(ou, "Company partner should auto-create an OU.")
        return partner, ou

    def _make_product(self, standard_price):
        return self.env["product.product"].create(
            {
                "name": "All-OU GP Product",
                "list_price": standard_price * 2,
                "standard_price": standard_price,  # company currency
            }
        )

    def _make_posted_invoice(self, partner, product, qty, price_unit):
        invoice = self.env["account.move"].create(
            {
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
        )
        invoice.action_post()
        return invoice

    # ------------------------------------------------------------------
    # Test 1: revenue-weighted formula, identical across OUs, weighting matters
    # ------------------------------------------------------------------

    def test_all_ou_revenue_weighted_gp(self):
        """
        Two OUs with known YTD invoices (single currency).

        OU A: 1 unit @ 100, cost 60  -> revenue 100, cost 60
              per-OU GP% = (100 - 60) / 100 = 0.40
        OU B: 3 units @ 100, cost 50 -> revenue 300, cost 150
              per-OU GP% = (300 - 150) / 300 = 0.50

        Revenue-weighted all-OU GP%:
            sum(revenue - cost) / sum(revenue)
          = ((100 - 60) + (300 - 150)) / (100 + 300)
          = (40 + 150) / 400 = 190 / 400 = 0.475

        A plain mean of the two per-OU percentages would be
        (0.40 + 0.50) / 2 = 0.45 -- so 0.475 proves the figure is
        revenue-weighted, not a simple average.
        """
        partner_a, ou_a = self._make_company("All-OU GP Partner A")
        partner_b, ou_b = self._make_company("All-OU GP Partner B")

        product_a = self._make_product(standard_price=60.0)
        product_b = self._make_product(standard_price=50.0)

        self._make_posted_invoice(partner_a, product_a, qty=1, price_unit=100.0)
        self._make_posted_invoice(partner_b, product_b, qty=3, price_unit=100.0)

        (ou_a | ou_b).invalidate_recordset()

        # AC-1: per-OU metrics are the expected unweighted margins.
        self.assertAlmostEqual(ou_a.avg_gross_profit_percentage, 0.40, places=4)
        self.assertAlmostEqual(ou_b.avg_gross_profit_percentage, 0.50, places=4)

        # AC-1 + AC-3: the all-OU figure is the revenue-weighted value 0.475,
        # distinct from the simple mean 0.45.
        self.assertAlmostEqual(
            ou_a.all_ou_avg_gross_profit_percentage,
            0.475,
            places=4,
            msg=(
                "All-OU GP% must be revenue-weighted: "
                "(40 + 150) / (100 + 300) = 0.475, not the plain mean 0.45."
            ),
        )
        self.assertNotAlmostEqual(
            ou_a.all_ou_avg_gross_profit_percentage,
            0.45,
            places=4,
            msg="Revenue-weighted figure must differ from the plain mean.",
        )

        # AC-2: the SAME rolled-up value lands on every OU record.
        self.assertAlmostEqual(
            ou_a.all_ou_avg_gross_profit_percentage,
            ou_b.all_ou_avg_gross_profit_percentage,
            places=6,
            msg="All-OU GP% must be identical across OU records.",
        )

    # ------------------------------------------------------------------
    # Test 2: divide-by-zero guard
    # ------------------------------------------------------------------

    def test_all_ou_gp_zero_revenue_guarded(self):
        """An OU with no qualifying YTD revenue yields 0.0, not an error."""
        _partner, ou = self._make_company("All-OU GP Empty Partner")
        ou.invalidate_recordset()
        self.assertEqual(
            ou.all_ou_avg_gross_profit_percentage,
            0.0,
            "With no qualifying revenue the all-OU GP% must be 0.0.",
        )
