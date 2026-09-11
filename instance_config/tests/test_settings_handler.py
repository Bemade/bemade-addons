"""The generic settings handler.

ACCEPTANCE CRITERIA
===================

`res.config.settings` is already a self-describing, symmetric mapping layer.
`_get_classified_fields()` (odoo/addons/base/models/res_config.py:178)
classifies EVERY settings field of EVERY installed module into:

    default_*         -> ir.default
    group_*           -> res.groups.implied_ids
    module_*          -> module install state
    config_parameter  -> ir.config_parameter
    other             -> company-related fields

`default_get()` reads them all (:245); `set_values()` writes them (:295) and
already skips no-ops (:312).

So this handler must NOT re-declare fields. It delegates, and its whole job is
to present that mapping as readable YAML and back. The tests exist to prove the
delegation is faithful and that it keeps working as modules come and go.

AC-1  Every field returned by `res.config.settings.fields_get()` is either
      emitted in the document or explicitly excluded by a named rule. Nothing
      is dropped by accident. This is what makes the handler auto-extend to
      modules that did not exist when it was written.

AC-2  Reading is delegated to `default_get`, not reimplemented. Asserted
      behaviourally: setting a value through the ordinary settings UI path and
      then reading produces that value.

AC-3  Writing is delegated to `create(vals).execute()`. Asserted by writing a
      `group_*` value and confirming the implied group actually moved on
      `res.groups`, and an `ir.config_parameter` value and confirming the
      parameter changed.

AC-4  Each classification round-trips: a `default_*`, a `group_*`, a
      `config_parameter` and an `other` field each survive read -> write ->
      read unchanged. One representative per class, not one per field.

AC-5  Readable aliases are OPTIONAL. An aliased setting emits under its pretty
      name (`analytic_accounting: on`); an unaliased one still emits under
      `settings.<field_name>`. Nothing is ever un-exportable merely because
      nobody curated a name for it.

AC-6  An alias and its underlying field are the same thing: writing via the
      alias and via `settings.<field_name>` produce identical state.

AC-7  An alias naming a field that does not exist (module not installed) is a
      clear error naming the alias, not a KeyError.

AC-8  A field present in the document but absent from this instance (its module
      is not installed) is reported, not silently ignored -- otherwise applying
      a config to the wrong instance looks like success.

AC-9  Company-scoped settings are read and written per company, so a two-company
      instance does not collapse to whichever company happened to be active.
"""

from odoo.tests import tagged

from ..tools.handler import Report
from ..tools.settings import (
    RULE_READONLY, RULE_TECHNICAL, SettingsHandler, TECHNICAL_FIELDS,
)
from .common import InstanceConfigCase


@tagged("post_install", "-at_install")
class TestSettingsHandler(InstanceConfigCase):

    def setUp(self):
        super().setUp()
        self.handler = SettingsHandler()

    def test_every_settings_field_is_emitted_or_excluded_by_rule(self):
        """AC-1: no accidental drops -- this is what makes it auto-extend."""
        report = Report()
        emitted = self.handler.read(self.env, report)
        settings = self.env["res.config.settings"]
        accounted = set(emitted) | {name for _d, name, _r in report.skipped}
        missing = set(settings._fields) - accounted
        self.assertFalse(
            missing,
            "fields neither emitted nor excluded by a named rule: %s"
            % sorted(missing),
        )

    def test_technical_fields_are_excluded_by_name(self):
        """AC-1: and the rule is recorded, not implicit."""
        report = Report()
        self.handler.read(self.env, report)
        skipped = {name: rule for _d, name, rule in report.skipped}
        for name in TECHNICAL_FIELDS & set(self.env["res.config.settings"]._fields):
            self.assertEqual(skipped.get(name), RULE_TECHNICAL)

    def test_read_reflects_a_value_set_through_settings(self):
        """AC-2: reading is delegated to default_get, not reimplemented."""
        settings = self.env["res.config.settings"]
        if "group_analytic_accounting" not in settings._fields:
            self.skipTest("analytic not installed")
        settings.create({"group_analytic_accounting": True}).execute()
        emitted = self.handler.read(self.env, Report())
        self.assertTrue(emitted["group_analytic_accounting"])

    def test_write_moves_the_implied_group(self):
        """AC-3: writing a group_* value actually moves res.groups."""
        settings = self.env["res.config.settings"]
        if "group_analytic_accounting" not in settings._fields:
            self.skipTest("analytic not installed")
        implied = self.env.ref("analytic.group_analytic_accounting")
        base_user = self.env.ref("base.group_user")
        settings.create({"group_analytic_accounting": False}).execute()
        self.assertNotIn(implied, base_user.all_implied_ids)

        report = Report()
        self.handler.write(self.env, {"group_analytic_accounting": True}, report)
        self.assertIn(implied, base_user.all_implied_ids)
        self.assertFalse(report.empty)

    def test_write_sets_a_config_parameter(self):
        """AC-3: and a config_parameter field reaches ir.config_parameter."""
        settings = self.env["res.config.settings"]
        field = next(
            (n for n, f in settings._fields.items()
             if getattr(f, "config_parameter", None) and f.type == "boolean"),
            None,
        )
        if not field:
            self.skipTest("no boolean config_parameter field available")
        param = settings._fields[field].config_parameter
        self.handler.write(self.env, {field: True}, Report())
        self.assertTrue(
            self.env["ir.config_parameter"].sudo().get_param(param))

    def test_writing_current_values_changes_nothing(self):
        """AC-4 of the round trip, at handler level: read then write is a no-op."""
        emitted = self.handler.read(self.env, Report())
        report = Report()
        self.handler.write(self.env, emitted, report)
        self.assertTrue(
            report.empty,
            "re-applying an instance's own settings reported changes: %s"
            % report.changes,
        )

    def test_unknown_field_in_document_is_reported(self):
        """AC-8: applying to the wrong instance must not look like success."""
        report = Report()
        self.handler.write(
            self.env, {"module_a_module_that_does_not_exist": True}, report)
        self.assertTrue(report.unhandled)
        self.assertIn(
            "a_module_that_does_not_exist", str(report.unhandled))

    def test_unknown_field_does_not_abort_the_rest(self):
        """AC-8: the gap is reported, the known settings still apply."""
        settings = self.env["res.config.settings"]
        if "group_analytic_accounting" not in settings._fields:
            self.skipTest("analytic not installed")
        settings.create({"group_analytic_accounting": False}).execute()
        report = Report()
        self.handler.write(self.env, {
            "module_a_module_that_does_not_exist": True,
            "group_analytic_accounting": True,
        }, report)
        self.assertTrue(report.unhandled)
        implied = self.env.ref("analytic.group_analytic_accounting")
        self.assertIn(implied, self.env.ref("base.group_user").all_implied_ids)

    def test_dry_run_reports_without_writing(self):
        """AC-8 of the round trip, at handler level."""
        settings = self.env["res.config.settings"]
        if "group_analytic_accounting" not in settings._fields:
            self.skipTest("analytic not installed")
        settings.create({"group_analytic_accounting": False}).execute()
        implied = self.env.ref("analytic.group_analytic_accounting")

        report = Report()
        self.handler.write(
            self.env, {"group_analytic_accounting": True}, report, dry_run=True)
        self.assertFalse(report.empty, "dry run should still report the change")
        self.assertNotIn(
            implied, self.env.ref("base.group_user").all_implied_ids,
            "dry run must not write",
        )

    def test_many2one_settings_are_not_emitted_as_raw_ids(self):
        """AC-3 of descriptors, enforced here: an id is meaningless elsewhere."""
        report = Report()
        emitted = self.handler.read(self.env, Report())
        self.handler.read(self.env, report)
        settings = self.env["res.config.settings"]
        for name, value in emitted.items():
            if settings._fields[name].type == "many2one":
                self.assertFalse(
                    value,
                    "%s emitted a raw id (%r); it should have been skipped "
                    "as unresolvable" % (name, value),
                )
