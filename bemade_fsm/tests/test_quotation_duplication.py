"""
Test cases for SO duplication with FSM visits.

Acceptance criteria:
1. Full SO duplication preserves visits linked to correct section lines with
   sale_order_id set.
2. Selective duplication (duplicate_all_lines=False) preserves visits for
   selected section lines and removes visits for unselected sections.
3. Visits on the new SO are independent copies — modifying them does not
   affect the originals.
4. Deleting an unselected section line cascade-deletes its visit, not visits
   belonging to other sections.
"""

from odoo.tests import tagged

from .test_bemade_fsm_common import BemadeFSMBaseTest


@tagged("-at_install", "post_install")
class TestQuotationDuplicationFSM(BemadeFSMBaseTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls._generate_partner()
        cls.product = cls._generate_product()

    def _create_so_with_two_visits(self):
        """Create an SO with two visit sections, each with a product line."""
        so = self._generate_sale_order(partner=self.partner)
        visit1 = self._generate_visit(so, label="Visit 1")
        sol1 = self._generate_sale_order_line(so, product=self.product)
        visit2 = self._generate_visit(so, label="Visit 2")
        sol2 = self._generate_sale_order_line(so, product=self.product)
        visit1.so_section_id.sequence = 1
        sol1.sequence = 2
        visit2.so_section_id.sequence = 3
        sol2.sequence = 4
        return so, visit1, sol1, visit2, sol2

    def test_full_duplication_preserves_visits(self):
        so, visit1, sol1, visit2, sol2 = self._create_so_with_two_visits()

        new_so = so.copy()

        self.assertEqual(len(new_so.visit_ids), 2)
        for visit in new_so.visit_ids:
            self.assertEqual(visit.sale_order_id, new_so)
            self.assertEqual(
                visit.so_section_id.display_type, "line_section"
            )
            self.assertIn(visit.so_section_id, new_so.order_line)

    def test_full_duplication_creates_independent_copies(self):
        so, visit1, sol1, visit2, sol2 = self._create_so_with_two_visits()

        new_so = so.copy()

        self.assertEqual(len(so.visit_ids), 2)
        self.assertFalse(new_so.visit_ids & so.visit_ids)

    def test_visit_labels_match_after_duplication(self):
        so, visit1, sol1, visit2, sol2 = self._create_so_with_two_visits()

        new_so = so.copy()

        original_labels = set(so.visit_ids.mapped("label"))
        new_labels = set(new_so.visit_ids.mapped("label"))
        self.assertEqual(original_labels, new_labels)
