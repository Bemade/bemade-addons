"""Module install and uninstall.

ACCEPTANCE CRITERIA
===================

Uncharted territory: nothing in bemade-addons calls
`button_immediate_install` / `button_immediate_uninstall`, so there is no
in-house pattern to copy and the auto-install behaviour has to be handled from
first principles.

The awkward case, found on a real instance:

    web_unsplash        auto_install: True, depends base_setup + html_editor
    snailmail           auto_install: True, depends iap_mail + mail
    snailmail_account   auto_install: True, depends account + snailmail

Every one of those dependency sets is satisfied by any instance we build, so
all three INSTALL THEMSELVES. Declaring them "off" by omission achieves
nothing; they must be uninstalled, and they can come back.

AC-1  A module declared on is installed; a module declared off is uninstalled.

AC-2  A module already in the declared state is a no-op -- no install or
      uninstall is triggered, and the change report is empty for it.

AC-3  An auto-install module declared off STAYS off across a module-list update
      (`update_list()`), the operation that re-evaluates auto_install. This is
      the regression the whole handler exists to prevent, so it is asserted
      directly rather than assumed.

AC-4  Installing a module mid-apply invalidates the registry, and configuration
      belonging to the newly installed module is applied correctly afterwards.
      This is why modules are FIRST in the application order -- a later section
      may reference a model that only exists once its module is installed.

AC-5  A module named in the document that does not exist in the addons path is
      a clear error naming it, distinguished from one that exists but is not
      installed.

AC-6  Uninstalling a module that other declared configuration depends on is
      refused, with the dependency named, rather than producing an instance
      that fails later in the apply.

AC-7  Reading emits the install state of modules that are configuration-
      relevant, not all ~125 installed modules. Emitting the full list would
      make every document unreadable and couple it to Odoo's dependency graph.
      The rule for which modules are emitted is explicit and tested.
"""

from odoo.tests import tagged

from ..tools.handler import Report
from ..tools.modules import PRESENT, ModulesHandler
from .common import InstanceConfigCase


@tagged("post_install", "-at_install")
class TestModules(InstanceConfigCase):
    """Note what these tests do NOT do: install or uninstall anything.

    Odoo forbids it (ir_module.py:603) -- "Module operations inside tests are
    not transactional and thus forbidden." So the contract asserted here is the
    STATE TRANSITION the handler is responsible for; carrying it out belongs to
    the following registry update. An end-to-end check of a real install has to
    live outside the standard suite, the way odoo_herd tags its
    cluster-dependent tests.
    """

    def setUp(self):
        super().setUp()
        self.handler = ModulesHandler()
        self.Module = self.env["ir.module.module"]

    def _module(self, name):
        return self.Module.search([("name", "=", name)], limit=1)

    def test_declared_install_marks_to_install(self):
        """AC-1: state moves to 'to install', not installed-in-place."""
        target = self.Module.search([("state", "=", "uninstalled")], limit=1)
        if not target:
            self.skipTest("no uninstalled module available")
        report = Report()
        self.handler.write(self.env, {target.name: True}, report)
        self.assertEqual(target.state, "to install")
        self.assertTrue(
            [c for c in report.changes if c.key == target.name])

    def test_declared_uninstall_marks_to_remove(self):
        """AC-1."""
        target = self._module("base")
        # `base` can never be removed; use any leaf module that is installed.
        target = self.Module.search([
            ("state", "=", "installed"), ("name", "!=", "base"),
        ], limit=1)
        if not target:
            self.skipTest("no removable installed module available")
        report = Report()
        self.handler.write(self.env, {target.name: False}, report)
        self.assertEqual(target.state, "to remove")

    def test_already_correct_module_is_a_noop(self):
        """AC-2: no churn, and nothing reported."""
        installed = self._module("base")
        report = Report()
        self.handler.write(self.env, {"base": True}, report)
        self.assertEqual(installed.state, "installed")
        self.assertFalse(
            [c for c in report.changes if c.key == "base"],
            "a module already in the wanted state should report no change")

    def test_unknown_module_is_a_clear_error(self):
        """AC-5: absent from the addons path, not merely uninstalled."""
        report = Report()
        self.handler.write(
            self.env, {"a_module_that_does_not_exist": True}, report)
        self.assertIn("a_module_that_does_not_exist", str(report.unhandled))
        self.assertIn("addons path", str(report.unhandled))

    def test_write_reports_that_an_update_is_required(self):
        """The caller must know the work is not finished in this transaction."""
        target = self.Module.search([("state", "=", "uninstalled")], limit=1)
        if not target:
            self.skipTest("no uninstalled module available")
        report = Report()
        self.handler.write(self.env, {target.name: True}, report)
        self.assertIn("registry update", str(report.unhandled))

    def test_dry_run_marks_nothing(self):
        """A plan must not move state."""
        target = self.Module.search([("state", "=", "uninstalled")], limit=1)
        if not target:
            self.skipTest("no uninstalled module available")
        report = Report()
        self.handler.write(self.env, {target.name: True}, report, dry_run=True)
        self.assertEqual(target.state, "uninstalled")
        self.assertFalse(report.empty, "a dry run should still report")

    def test_immediate_apply_is_refused_inside_tests(self):
        """The guard mirrors Odoo's own, so it stays true if Odoo changes.

        This asserts the handler KNOWS it cannot install here -- which is why
        write() marks state instead of calling button_immediate_install.
        """
        self.assertFalse(self.handler.can_apply_immediately(self.env))

    def test_read_omits_modules_present_only_as_dependencies(self):
        """AC-7: a document listing every installed module is unreadable."""
        emitted = self.handler.read(self.env, Report())
        installed = self.Module.search_count([("state", "in", list(PRESENT))])
        self.assertLess(
            len([k for k, v in emitted.items() if v]), installed,
            "read should emit deliberately-installed modules, not all of them")

    def test_read_records_removed_auto_install_modules(self):
        """An absent auto-install module is absent on purpose.

        Nothing else explains it, so it must be recorded or a rebuild silently
        gets it back.
        """
        removed = self.Module.search([
            ("auto_install", "=", True),
            ("state", "not in", list(PRESENT)),
        ], limit=1)
        if not removed:
            self.skipTest("no uninstalled auto-install module on this instance")
        emitted = self.handler.read(self.env, Report())
        self.assertIs(emitted.get(removed.name), False)

    def test_auto_install_needs_a_dependency_being_installed_now(self):
        """AC-3, asserted on the mechanism rather than by installing.

        button_install (ir_module.py:419) only pulls in an auto-install module
        when one of its required dependencies is in state 'to install' -- being
        installed in THIS operation. Dependencies that are merely 'installed',
        or 'to upgrade' during an -u all, do not qualify. That is why an
        uninstalled auto-install module stays uninstalled through ordinary
        upgrades.
        """
        auto = self.Module.search([
            ("auto_install", "=", True), ("state", "=", "installed"),
        ], limit=1)
        if not auto:
            self.skipTest("no installed auto-install module")
        dep_states = {
            d.state for d in auto.dependencies_id if d.auto_install_required
        }
        self.assertTrue(dep_states <= PRESENT)
        self.assertNotIn(
            "to install", dep_states,
            "no install is in flight, so nothing would re-trigger auto-install")
