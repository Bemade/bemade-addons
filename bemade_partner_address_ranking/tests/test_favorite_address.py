# Copyright (C) 2024 Bemade Inc. (<https://www.bemade.org>).
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
"""
Acceptance criteria for bemade_partner_address_ranking
=======================================================

1.  Cold-start fallback: new SO with no prior history picks stock address_get result.
2.  Manual override beats ranking: is_favorite_invoice=True on contact B beats A even
    if A has 5 confirmed SOs as invoice.
3.  Ranking picks highest count: no favorite; B used 5×, A used 3× → B wins.
    Symmetric for delivery.
4.  Tiebreaker: two contacts used equally (2× each) → falls through to address_get.
5.  UI checkbox saves and toggles correctly (via Form proxy).
6.  Constraint enforces one favorite per address type per company; cross-type allowed.
7.  Draft/cancelled SOs ignored: only confirmed/done count for ranking.
8.  Standalone partner (no parent) with is_favorite_invoice=True raises no constraint error
    and ranking helper returns address_get fallback.
9.  Backward compatibility: existing SO keeps its addresses on resave (compute only on
    partner_id change).
10. name_search orders favorite first when context key is present.
11. name_search orders by usage rank when no favorite.
12. name_search unchanged for non-company context (no partner_address_ranking key).
13. name_search preserves user-typed text filter (typed text limits results; favorite
    that doesn't match is excluded).
14. name_search respects limit: 50 candidates → exactly limit=10 returned.
15. name_search promotes the favorite even when it falls outside the limit window
    (the web client asks for limit=8 and the base page is ordered by name).
16. name_search resolves the company from 'default_parent_id' — the context key the
    stock sale.order address fields actually send.
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests.form import Form
from odoo.tools.misc import mute_logger


def _confirm_so(env, partner, invoice_partner, shipping_partner):
    """Create and confirm a sale order with explicit invoice/shipping partners."""
    so = env["sale.order"].create(
        {
            "partner_id": partner.id,
            "partner_invoice_id": invoice_partner.id,
            "partner_shipping_id": shipping_partner.id,
        }
    )
    so.action_confirm()
    return so


class TestFavoriteAddress(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Grant the test user access to invoice/delivery address fields on the
        # SO form (the partner_shipping_id field is gated by this group).
        group = cls.env.ref("account.group_delivery_invoice_address")
        cls.env.user.groups_id |= group

        Partner = cls.env["res.partner"]

        cls.company = Partner.create({"name": "ACME Corp", "is_company": True})
        cls.addr_invoice = Partner.create(
            {"name": "Billing Dept", "parent_id": cls.company.id, "type": "invoice"}
        )
        cls.addr_delivery = Partner.create(
            {"name": "Shipping Dock", "parent_id": cls.company.id, "type": "delivery"}
        )
        cls.addr_other = Partner.create(
            {"name": "Other Contact", "parent_id": cls.company.id, "type": "other"}
        )

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _open_so_form(self, partner):
        """Open a new SO Form with the given partner and return it."""
        f = Form(self.env["sale.order"])
        f.partner_id = partner
        return f

    # ------------------------------------------------------------------
    # Test cases
    # ------------------------------------------------------------------

    def test_01_cold_start_fallback(self):
        """AC1: No history → stock address_get is used."""
        f = self._open_so_form(self.company)
        expected_invoice = self.company.address_get(["invoice"])["invoice"]
        expected_delivery = self.company.address_get(["delivery"])["delivery"]
        self.assertEqual(f.partner_invoice_id.id, expected_invoice)
        self.assertEqual(f.partner_shipping_id.id, expected_delivery)

    def test_02_favorite_beats_ranking(self):
        """AC2: is_favorite_invoice on B wins even when A has 5 confirmed SOs."""
        # Create 5 confirmed SOs using addr_invoice (A) as invoice
        for _ in range(5):
            _confirm_so(
                self.env, self.company, self.addr_invoice, self.addr_delivery
            )
        # Mark the other address as favorite
        self.addr_other.is_favorite_invoice = True
        try:
            f = self._open_so_form(self.company)
            self.assertEqual(f.partner_invoice_id, self.addr_other)
        finally:
            self.addr_other.is_favorite_invoice = False

    def test_03_ranking_picks_highest_count(self):
        """AC3: No favorites; B used 5×, A used 3× as invoice → B wins.
        Symmetric: addr_other used more as shipping than addr_delivery → wins."""
        # 3 SOs with addr_invoice (A) as invoice; addr_delivery as shipping
        for _ in range(3):
            _confirm_so(self.env, self.company, self.addr_invoice, self.addr_delivery)
        # 5 SOs with addr_other (B) as invoice; addr_delivery as shipping
        for _ in range(5):
            _confirm_so(self.env, self.company, self.addr_other, self.addr_delivery)

        # After the above loops: addr_other has 5 invoice uses; addr_invoice has 3.
        f = self._open_so_form(self.company)
        self.assertEqual(f.partner_invoice_id, self.addr_other)

        # Symmetric for delivery: at this point addr_delivery has 8 shipping uses.
        # We add 10 SOs with addr_other as shipping to ensure addr_other wins.
        for _ in range(10):
            _confirm_so(self.env, self.company, self.addr_invoice, self.addr_other)
        f2 = self._open_so_form(self.company)
        self.assertEqual(f2.partner_shipping_id, self.addr_other)

    def test_04_tiebreaker_falls_to_address_get(self):
        """AC4: Equal usage → falls through to stock address_get."""
        for _ in range(2):
            _confirm_so(self.env, self.company, self.addr_invoice, self.addr_delivery)
        for _ in range(2):
            _confirm_so(self.env, self.company, self.addr_other, self.addr_delivery)

        expected_invoice = self.company.address_get(["invoice"])["invoice"]
        f = self._open_so_form(self.company)
        self.assertEqual(f.partner_invoice_id.id, expected_invoice)

    def test_05_ui_checkbox_toggles(self):
        """AC5: Form proxy can tick/untick is_favorite_invoice."""
        with Form(self.addr_invoice) as pf:
            pf.is_favorite_invoice = True
        self.assertTrue(self.addr_invoice.is_favorite_invoice)
        with Form(self.addr_invoice) as pf:
            pf.is_favorite_invoice = False
        self.assertFalse(self.addr_invoice.is_favorite_invoice)

    def test_06_constraint_one_favorite_per_type(self):
        """AC6: Two contacts with same is_favorite_invoice raise ValidationError;
        one invoice + one delivery is allowed."""
        self.addr_invoice.is_favorite_invoice = True
        try:
            with mute_logger("odoo.sql_db"):
                with self.assertRaises(ValidationError):
                    self.addr_other.is_favorite_invoice = True

            # Cross-type should be allowed
            self.addr_other.is_favorite_delivery = True
            self.assertTrue(self.addr_other.is_favorite_delivery)
        finally:
            self.addr_invoice.is_favorite_invoice = False
            self.addr_other.is_favorite_invoice = False
            self.addr_other.is_favorite_delivery = False

    def test_07_draft_cancelled_ignored(self):
        """AC7: Only confirmed/done SOs count; draft+cancelled for A, 1 confirmed for B."""
        # 3 draft SOs with addr_invoice
        for _ in range(3):
            self.env["sale.order"].create(
                {
                    "partner_id": self.company.id,
                    "partner_invoice_id": self.addr_invoice.id,
                    "partner_shipping_id": self.addr_delivery.id,
                }
            )
        # 2 cancelled SOs with addr_invoice
        for _ in range(2):
            so = self.env["sale.order"].create(
                {
                    "partner_id": self.company.id,
                    "partner_invoice_id": self.addr_invoice.id,
                    "partner_shipping_id": self.addr_delivery.id,
                }
            )
            so.action_cancel()
        # 1 confirmed SO with addr_other
        _confirm_so(self.env, self.company, self.addr_other, self.addr_delivery)

        f = self._open_so_form(self.company)
        self.assertEqual(f.partner_invoice_id, self.addr_other)

    def test_08_standalone_partner_no_constraint_error(self):
        """AC8: Partner with no parent can set is_favorite_invoice; ranking returns
        address_get fallback."""
        standalone = self.env["res.partner"].create({"name": "Standalone Co", "is_company": True})
        # No constraint error expected
        standalone.is_favorite_invoice = True
        # Ranking should still return a sensible fallback
        ranked = standalone._get_ranked_address_ids("invoice")
        self.assertTrue(len(ranked) >= 1)
        fallback = standalone.address_get(["invoice"])["invoice"]
        self.assertIn(fallback, ranked)

    def test_09_backward_compatibility(self):
        """AC9: Pre-existing SO keeps its addresses on resave (compute only on
        partner_id change)."""
        so = _confirm_so(self.env, self.company, self.addr_invoice, self.addr_delivery)
        original_invoice = so.partner_invoice_id
        original_shipping = so.partner_shipping_id
        # Resave without touching partner_id
        so.write({"note": "Updated note"})
        self.assertEqual(so.partner_invoice_id, original_invoice)
        self.assertEqual(so.partner_shipping_id, original_shipping)

    def test_10_name_search_favorite_first(self):
        """AC10: name_search with partner_address_ranking context puts favorite first."""
        self.addr_other.is_favorite_invoice = True
        try:
            results = self.env["res.partner"].with_context(
                partner_address_ranking="invoice",
                default_commercial_partner_id=self.company.id,
            ).name_search(
                "",
                args=[("parent_id", "=", self.company.id)],
            )
            result_ids = [r[0] for r in results]
            self.assertIn(self.addr_other.id, result_ids)
            self.assertEqual(result_ids[0], self.addr_other.id)
        finally:
            self.addr_other.is_favorite_invoice = False

    def test_11_name_search_usage_rank(self):
        """AC11: name_search orders by usage rank when no favorite."""
        # A used 5×, B used 2×, C (addr_delivery) used 0×
        for _ in range(5):
            _confirm_so(self.env, self.company, self.addr_invoice, self.addr_delivery)
        for _ in range(2):
            _confirm_so(self.env, self.company, self.addr_other, self.addr_delivery)

        results = self.env["res.partner"].with_context(
            partner_address_ranking="invoice",
            default_commercial_partner_id=self.company.id,
        ).name_search(
            "",
            args=[("parent_id", "=", self.company.id)],
        )
        result_ids = [r[0] for r in results]
        # addr_invoice (5×) should come before addr_other (2×)
        self.assertIn(self.addr_invoice.id, result_ids)
        self.assertIn(self.addr_other.id, result_ids)
        self.assertLess(
            result_ids.index(self.addr_invoice.id),
            result_ids.index(self.addr_other.id),
        )

    def test_12_name_search_unchanged_without_context(self):
        """AC12: Plain name_search without partner_address_ranking context returns
        standard unmodified results."""
        standard = self.env["res.partner"].name_search("ACME Corp")
        # Should not raise and should return results in normal alphabetical order
        self.assertTrue(any(r[0] == self.company.id for r in standard))

    def test_13_name_search_preserves_text_filter(self):
        """AC13: Typed text still filters; favorite that doesn't match is excluded.

        We use a fresh company whose name does NOT contain the search term, so
        searching for "InvoiceOnly" only matches the billing contact and not the
        favorite contact "OtherFav".
        """
        # Use a dedicated company so its name won't match the search term.
        test_company = self.env["res.partner"].create(
            {"name": "Filter Test Corp", "is_company": True}
        )
        billing = self.env["res.partner"].create(
            {"name": "InvoiceOnly Contact", "parent_id": test_company.id, "type": "invoice"}
        )
        fav = self.env["res.partner"].create(
            {"name": "OtherFav Contact", "parent_id": test_company.id, "type": "other"}
        )
        fav.is_favorite_invoice = True
        try:
            results = self.env["res.partner"].with_context(
                partner_address_ranking="invoice",
                default_commercial_partner_id=test_company.id,
            ).name_search(
                "InvoiceOnly",
                args=[("parent_id", "=", test_company.id)],
            )
            result_ids = [r[0] for r in results]
            # "InvoiceOnly Contact" matches the search term
            self.assertIn(billing.id, result_ids)
            # "OtherFav Contact" is the favorite but does NOT contain "InvoiceOnly"
            # and "Filter Test Corp" also does not contain "InvoiceOnly",
            # so the favorite should be excluded from results.
            self.assertNotIn(fav.id, result_ids)
        finally:
            fav.is_favorite_invoice = False

    def test_14_name_search_respects_limit(self):
        """AC14: With many candidates and limit=10, exactly 10 are returned."""
        # Create 50 child contacts for a fresh company
        big_company = self.env["res.partner"].create(
            {"name": "Big Corp", "is_company": True}
        )
        children = self.env["res.partner"].create(
            [
                {"name": f"Contact {i:02d}", "parent_id": big_company.id}
                for i in range(50)
            ]
        )
        # Mark first child as favorite so ranking logic is exercised
        children[0].is_favorite_invoice = True

        results = self.env["res.partner"].with_context(
            partner_address_ranking="invoice",
            default_commercial_partner_id=big_company.id,
        ).name_search(
            "",
            args=[("parent_id", "=", big_company.id)],
            limit=10,
        )
        self.assertEqual(len(results), 10)
        # Favorite should still be first
        self.assertEqual(results[0][0], children[0].id)

    def test_15_favorite_promoted_from_outside_limit_window(self):
        """AC15: the favorite is promoted even when it is not in the base page.

        The web client asks for limit=8 and the underlying page is ordered by
        display_name, so a company's own addresses are usually not in it. A
        reorder-in-place would find nothing to promote and silently return the
        unranked page — this asserts the ranked address is fetched instead.
        """
        company = self.env["res.partner"].create(
            {"name": "Zulu Holdings", "is_company": True}
        )
        # Alphabetically-early decoys that will fill the whole limit window.
        self.env["res.partner"].create(
            [{"name": f"Aaa Decoy {i:02d}"} for i in range(20)]
        )
        favorite = self.env["res.partner"].create(
            {
                "name": "Zzz Invoice Contact",
                "parent_id": company.id,
                "type": "invoice",
                "is_favorite_invoice": True,
            }
        )

        results = self.env["res.partner"].with_context(
            partner_address_ranking="invoice",
            default_parent_id=company.id,
        ).name_search("", args=[], limit=8)

        self.assertEqual(len(results), 8, "limit must still be honoured")
        self.assertEqual(
            results[0][0],
            favorite.id,
            "favorite must be promoted even though it sorts after the "
            "limit window of the base search",
        )

    def test_16_ranking_resolves_from_default_parent_id(self):
        """AC16: 'default_parent_id' resolves the company.

        That is the key the stock sale.order form puts on partner_invoice_id /
        partner_shipping_id; those fields carry no domain, so it is the only
        signal the real picker sends.
        """
        company = self.env["res.partner"].create(
            {"name": "Yankee Ltd", "is_company": True}
        )
        plain = self.env["res.partner"].create(
            {"name": "Aaa Plain Contact", "parent_id": company.id, "type": "invoice"}
        )
        favorite = self.env["res.partner"].create(
            {
                "name": "Bbb Favorite Contact",
                "parent_id": company.id,
                "type": "invoice",
                "is_favorite_invoice": True,
            }
        )

        # NO parent_id leaf in args: the stock sale.order address fields carry
        # no domain, so the context key must be sufficient on its own. Passing a
        # domain here would let the args-scan resolve the company and the test
        # would pass even with the context key unhandled.
        results = self.env["res.partner"].with_context(
            partner_address_ranking="invoice",
            default_parent_id=company.id,
        ).name_search("", args=[], limit=10)

        ids = [r[0] for r in results]
        self.assertEqual(
            ids[0],
            favorite.id,
            "favorite must rank first when the company comes from "
            "default_parent_id",
        )
        self.assertIn(plain.id, ids)
