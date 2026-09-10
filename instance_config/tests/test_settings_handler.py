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

from .common import InstanceConfigCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSettingsHandler(InstanceConfigCase):

    def test_every_settings_field_is_emitted_or_excluded_by_rule(self):
        """AC-1: no accidental drops; this is what makes it auto-extend."""
        self.skipTest("not implemented")

    def test_read_reflects_values_set_through_settings(self):
        """AC-2."""
        self.skipTest("not implemented")

    def test_write_moves_groups_and_parameters(self):
        """AC-3: implied group moves, ir.config_parameter changes."""
        self.skipTest("not implemented")

    def test_each_classification_round_trips(self):
        """AC-4: default / group / config / other, one each."""
        self.skipTest("not implemented")

    def test_unaliased_settings_still_export(self):
        """AC-5."""
        self.skipTest("not implemented")

    def test_alias_and_raw_field_are_equivalent(self):
        """AC-6."""
        self.skipTest("not implemented")

    def test_unknown_field_in_document_is_reported(self):
        """AC-8: applying to the wrong instance must not look like success."""
        self.skipTest("not implemented")

    def test_company_scoped_settings_are_per_company(self):
        """AC-9."""
        self.skipTest("not implemented")
