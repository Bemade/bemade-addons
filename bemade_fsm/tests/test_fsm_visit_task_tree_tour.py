# Copyright (C) 2024 Bemade Inc. (<https://www.bemade.org>).
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
"""JS-tour test for the visit "Full Task Tree" view/action (task 3360).

This is the browser-rendered counterpart of test_fsm_visit_task_tree.py. The
Python unit tests there validate the server-side contract (arch builds, the
action domain resolves the visit root, the full descendant set is reachable).
They cannot, however, prove that the recursive list view *renders* the tree
correctly and that the client-side lazy-expand actually works -- a typo in the
view xpath, a wrong context attribute, the recursive="1" flag failing to wire
the recursive_list_view renderer/controller, or the expand bus event breaking
would all slip past pure-Python tests.

This HttpCase drives the real feature in a browser:
  1. seeds one confirmed sale order whose single visit has a known multi-level
     task tree (visit root -> Parent -> Child -> Grandchild -> Great-grandchild,
     via the [2,2,2] template fixture), then
  2. runs the `fsm_visit_task_tree_tour` JS tour, which opens the SO form, opens
     the Field Service page, clicks the per-row "Full Task Tree" button, and
     asserts the recursive task list renders the multi-level structure and that
     lazy-expand reveals deeper levels (depth 0 -> 1 -> 2).

AC (from tour assertions):
- The "Full Task Tree" button on the visit row opens the recursive task list
  action (recursive expand column present).
- The visit's root task renders as an expandable root row.
- Expanding the root reveals depth-1 children; expanding a child reveals depth-2
  grandchildren -- i.e. the rendered tree is genuinely multi-level and the
  lazy-expand is functional.
"""
import odoo.tests
from odoo.tests import tagged

from .test_bemade_fsm_common import BemadeFSMBaseTest


@tagged("post_install", "-at_install")
class FSMVisitTaskTreeTourTest(odoo.tests.HttpCase, BemadeFSMBaseTest):
    def test_full_task_tree_tour(self):
        """Drive the visit "Full Task Tree" recursive list in a browser and
        assert the multi-level structure renders and lazy-expand works."""
        # Seed one confirmed SO with a single visit whose root task has a
        # [2,2,2] descendant structure (Parent -> Child -> Grandchild ->
        # Great-grandchild), all grouped under the visit root task.
        (
            so,
            visit,
            _sol1,
            _sol2,
        ) = self._generate_so_with_one_visit_two_lines_and_descendants()
        so.action_confirm()

        # Sanity-check the seed so a tour failure can't be masked by missing
        # data: the visit must have a root task and a genuinely multi-level
        # subtree reachable from it.
        root = visit.task_id
        self.assertTrue(root, "Seed must produce a visit root task")
        full_tree = root._get_full_hierarchy()
        self.assertTrue(root.child_ids, "Root must have immediate children")
        self.assertTrue(
            full_tree - root - root.child_ids,
            "Seed tree must be multi-level (grandchildren+) for the tour to "
            "exercise lazy-expand beyond immediate children",
        )

        # Open the tour on the seeded sale order form so the visit row (and its
        # "Full Task Tree" button) is one click away.
        self.start_tour(
            f"/odoo/sales/{so.id}",
            "fsm_visit_task_tree_tour",
            login="admin",
        )
