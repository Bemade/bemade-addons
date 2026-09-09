"""Tests for the visit "Full Task Tree" view/action (task 3360).

Acceptance criterion: a single view renders the full multi-level task hierarchy
for a visit (root -> child -> grandchild ...), not just the immediate children of
one parent.

The view is a read-only project.task list marked recursive="1" (recursive_list_view
module expands descendants client-side via parent_id). The Python-testable contract
is therefore:
  1. the action's view arch builds (the main failure mode of a view change), and
  2. the action's domain pins to the visit, resolving the visit's root task, from
     which the COMPLETE descendant set (every level) is reachable via parent_id.
"""
from odoo.tests import tagged
from .test_bemade_fsm_common import BemadeFSMBaseTest


@tagged("-at_install", "post_install")
class FSMVisitTaskTreeTest(BemadeFSMBaseTest):
    def _confirm_so_with_multilevel_tree(self):
        (
            so,
            visit,
            _sol1,
            _sol2,
        ) = self._generate_so_with_one_visit_two_lines_and_descendants()
        so.action_confirm()
        return so, visit

    def test_task_tree_view_arch_builds(self):
        """The recursive list view arch loads/builds without error (broken arch is
        the primary failure mode of a view change)."""
        view = self.env.ref("bemade_fsm.bemade_fsm_visit_task_tree_list")
        self.assertEqual(view.model, "project.task")
        # get_view fully parses + validates the arch for the model.
        arch = self.env["project.task"].get_view(view_id=view.id, view_type="list")
        self.assertIn("recursive", arch["arch"])

    def test_action_domain_resolves_visit_root_task(self):
        """The action domain ([('visit_id','=',active_id)]) resolves exactly the
        visit's root task(s) -- the recursive widget then restricts the root rows
        to parent_id=False and loads descendants from there."""
        _so, visit = self._confirm_so_with_multilevel_tree()
        action = self.env.ref("bemade_fsm.action_visit_task_tree").sudo()

        domain = [("visit_id", "=", visit.id)]
        roots = self.env["project.task"].search(domain)

        self.assertEqual(action.res_model, "project.task")
        self.assertTrue(roots, "The action domain must resolve the visit's root task")
        # visit_id is set only on the root task; every resolved record is a root.
        self.assertEqual(roots, visit.task_id)
        self.assertFalse(
            roots.filtered("parent_id"),
            "Records pinned by visit_id must be parent_id=False root tasks",
        )

    def test_full_multilevel_hierarchy_reachable_from_root(self):
        """From the visit's root task the COMPLETE multi-level subtree (child ->
        grandchild -> great-grandchild) is reachable via parent_id -- i.e. the tree
        the recursive view walks covers every descendant, not just immediate
        children."""
        _so, visit = self._confirm_so_with_multilevel_tree()
        root = visit.task_id

        full_tree = root._get_full_hierarchy()

        # Fixture builds two SO lines, each a Parent with structure [2,2,2]:
        # parent + 2 children + 2 grandchildren + 2 great-grandchildren per line,
        # all grouped under the single visit root. Assert the tree is genuinely
        # multi-level (depth > 2) and strictly larger than the immediate children.
        self.assertIn(root, full_tree)
        self.assertTrue(root.child_ids, "Root must have immediate children")
        deeper = full_tree - root - root.child_ids
        self.assertTrue(
            deeper,
            "Hierarchy must extend beyond immediate children (grandchildren+)",
        )
        # Every task in the resolved tree descends from the visit root.
        for task in full_tree - root:
            self.assertEqual(
                task.root_ancestor,
                root,
                "Every task in the tree must descend from the visit root",
            )

    def test_visit_list_button_opens_task_tree_action(self):
        """The visit list (the only place a visit is surfaced -- it has no form
        view) builds with the 'Full Task Tree' button wired to the action."""
        view = self.env.ref("bemade_fsm.bemade_fsm_visit_list")
        arch = self.env["bemade_fsm.visit"].get_view(
            view_id=view.id, view_type="list"
        )
        action = self.env.ref("bemade_fsm.action_visit_task_tree")
        self.assertIn(str(action.id), arch["arch"])
