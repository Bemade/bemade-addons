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

from .common import InstanceConfigCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestModules(InstanceConfigCase):

    def test_declared_state_is_applied(self):
        """AC-1."""
        self.skipTest("not implemented")

    def test_already_correct_module_is_a_noop(self):
        """AC-2."""
        self.skipTest("not implemented")

    def test_auto_install_module_stays_uninstalled(self):
        """AC-3: the regression this handler exists to prevent."""
        self.skipTest("not implemented")

    def test_registry_reload_lets_later_sections_apply(self):
        """AC-4: why modules come first in the order."""
        self.skipTest("not implemented")

    def test_unknown_module_is_a_clear_error(self):
        """AC-5."""
        self.skipTest("not implemented")

    def test_uninstall_of_depended_on_module_is_refused(self):
        """AC-6."""
        self.skipTest("not implemented")

    def test_only_relevant_modules_are_emitted(self):
        """AC-7: a document listing 125 modules is unreadable."""
        self.skipTest("not implemented")
