# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""The module install/uninstall handler.

Odoo draws a hard line here, and this handler stays on the safe side of it.
``_button_immediate_function`` (base/models/ir_module.py:599) refuses to run
in two situations::

    if not self.env.registry.ready or self.env.registry._init:
        raise UserError('... cannot be called on init or non loaded
                         registries. Please use button_install instead.')
    if modules.module.current_test:
        raise RuntimeError("Module operations inside tests are not
                            transactional and thus forbidden.")

Provisioning happens exactly when the registry is being built, and the suite
runs inside tests, so the immediate variants are unavailable to us in both of
the places this code matters most.

The supported alternative is the one the error message names: ``button_install``
and ``button_uninstall`` only move ``ir.module.module.state`` to ``to install``
/ ``to remove``. That write is transactional, legal during init, legal in
tests, and the work itself happens on the next registry update -- a restart, an
``odoo -u``, or the operator's init step. So this handler PLANS, and reports
that an update is required; it does not try to install in-process.

On auto-install modules
-----------------------

``web_unsplash``, ``snailmail`` and ``snailmail_account`` declare
``auto_install: True`` with dependencies any instance satisfies, so they
install themselves and cannot be kept out by omission alone.

They are, however, less persistent than they first appear. ``button_install``
only pulls in an auto-install module when one of its required dependencies is
in state ``to install`` -- being installed in the current operation::

    states = {dep.state for dep in module.dependencies_id
              if dep.auto_install_required}
    return states <= install_states and 'to install' in states and ...

Dependencies that are merely ``installed``, or ``to upgrade`` during an
``-u all``, do not satisfy it. So an uninstalled auto-install module stays
uninstalled through ordinary upgrades; the only window is a FRESH install of
one of its dependencies. Worth knowing, because it means this handler has to
re-assert on every apply, but does not have to fight a losing battle.
"""

from odoo import _
from odoo.modules import module as module_lib

from .handler import Handler, register

#: States meaning "this module is, or is about to be, present".
PRESENT = frozenset({"installed", "to install", "to upgrade"})


@register
class ModulesHandler(Handler):

    domain = "modules"
    #: First: a later section may reference a model that only exists once its
    #: module is installed.
    order = 10

    # -- reading ---------------------------------------------------------

    def read(self, env, report):
        """Emit the state of modules that are configuration-relevant.

        Not all installed modules: a document listing every one of an
        instance's ~125 modules would be unreadable and would couple it to
        Odoo's dependency graph, so that adding one app rewrites the file.
        Only modules that were installed deliberately are emitted -- those not
        pulled in as a dependency of something else -- plus any auto-install
        module that has been deliberately removed.
        """
        Module = env["ir.module.module"]
        out = {}

        for module in Module.search([("state", "in", list(PRESENT))]):
            if self._is_only_a_dependency(env, module):
                continue
            out[module.name] = True

        # Auto-install modules that are absent are absent ON PURPOSE -- nothing
        # else would explain it -- so record them, or a rebuild silently gets
        # them back.
        for module in Module.search([
            ("auto_install", "=", True),
            ("state", "not in", list(PRESENT)),
        ]):
            out[module.name] = False

        return out

    def _is_only_a_dependency(self, env, module):
        """True when something else present depends on this module."""
        return bool(env["ir.module.module.dependency"].search_count([
            ("name", "=", module.name),
            ("module_id.state", "in", list(PRESENT)),
        ]))

    # -- writing ---------------------------------------------------------

    def write(self, env, data, report, dry_run=False):
        if not data:
            return
        Module = env["ir.module.module"]
        to_install = Module.browse()
        to_remove = Module.browse()

        for name, wanted in sorted(data.items()):
            module = Module.search([("name", "=", name)], limit=1)
            if not module:
                # Distinguished from "exists but not installed": a name absent
                # from the addons path is a typo or a missing repo, not a
                # configuration choice.
                report.gap(self.domain, _(
                    "module %(name)s is not in the addons path", name=name))
                continue
            present = module.state in PRESENT
            if wanted and not present:
                report.change(self.domain, name, module.state, "to install")
                to_install |= module
            elif not wanted and present:
                report.change(self.domain, name, module.state, "to remove")
                to_remove |= module
            # else: already in the wanted state -- no churn.

        if dry_run or (not to_install and not to_remove):
            return

        # State only. See the module docstring: the immediate variants are
        # illegal during init and inside tests, which is where this runs.
        if to_install:
            to_install.button_install()
        if to_remove:
            to_remove.button_uninstall()

        report.gap(self.domain, _(
            "%(count)s module(s) marked; a registry update (restart or "
            "'odoo -u') is required to carry it out.",
            count=len(to_install) + len(to_remove),
        ))

    # -- optional in-process completion -----------------------------------

    def can_apply_immediately(self, env):
        """Whether ``button_immediate_*`` is legal in this context.

        Mirrors Odoo's own two guards rather than guessing, so this stays true
        if they change.
        """
        return (
            env.registry.ready
            and not env.registry._init
            and not module_lib.current_test
        )
