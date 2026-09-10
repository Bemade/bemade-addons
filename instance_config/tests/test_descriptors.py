"""Record descriptors and field inference.

ACCEPTANCE CRITERIA
===================

Settings are covered generically by res.config.settings. RECORDS are not:
companies, users, mail servers, journals and the like are ordinary records, and
which of them constitute "configuration" is a judgement no metadata encodes.

That judgement is expressed as a DESCRIPTOR shipped as data -- about five lines
per model, never one per field:

    res.company:      {key: name,  order: 10, include: [logo]}
    res.users:        {key: login, order: 60, exclude: [password]}
    ir.mail_server:   {key: name,  order: 50, secret: [smtp_pass]}

The field list is INFERRED from `_fields`. Descriptors name only the exceptions.

AC-1  Field inference includes stored, writable fields and excludes: audit
      fields (`create_uid`, `create_date`, `write_uid`, `write_date`, `id`,
      `display_name`), computed fields with no inverse, and one2many fields
      that are the inverse of an included many2one (which would duplicate the
      same data on both sides).

AC-2  Binary fields are excluded unless named in `include`. `res.company.logo`
      is included and round-trips byte-identically.

AC-3  Many2one values are emitted as NATURAL KEYS, never database ids, so a
      document written from one database applies to another. A many2one to a
      model with no descriptor is an error naming both models, not a raw id
      silently emitted.

AC-4  Records are matched on their descriptor `key`, so applying a document to
      a database where the record already exists UPDATES it rather than
      creating a duplicate.

AC-5  `order` governs application sequence, and a descriptor whose many2one
      targets a model with a HIGHER order is a configuration error caught at
      load time -- not a runtime failure halfway through an apply.

AC-6  A field added to a model by a module installed later is picked up by
      inference with no descriptor change. Asserted by adding a field to a
      test model and confirming it appears.

AC-7  Fields named in `secret` are emitted as `!secret` references and never as
      values, exactly as in AC-5 of the round-trip suite.

AC-8  A record present in the instance but absent from the document is
      REPORTED, and removal requires an explicit flag. Silent deletion of
      configuration nobody declared is the wrong default.

AC-9  Descriptors are data, not code: adding one requires no Python. Asserted
      by loading a descriptor for a model with no bespoke handler and
      round-tripping it.
"""

from .common import InstanceConfigCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDescriptors(InstanceConfigCase):

    def test_field_inference_excludes_audit_and_computed(self):
        """AC-1."""
        self.skipTest("not implemented")

    def test_binary_excluded_unless_included(self):
        """AC-2: logo round-trips byte-identically."""
        self.skipTest("not implemented")

    def test_many2one_emitted_as_natural_key(self):
        """AC-3: and an undescribed target is an error, not a raw id."""
        self.skipTest("not implemented")

    def test_existing_record_is_updated_not_duplicated(self):
        """AC-4."""
        self.skipTest("not implemented")

    def test_bad_ordering_is_caught_at_load_time(self):
        """AC-5: not halfway through an apply."""
        self.skipTest("not implemented")

    def test_new_field_is_picked_up_without_descriptor_change(self):
        """AC-6: inference is what keeps descriptors short."""
        self.skipTest("not implemented")

    def test_extra_records_are_reported_not_deleted(self):
        """AC-8: silent deletion is the wrong default."""
        self.skipTest("not implemented")

    def test_descriptor_only_model_round_trips(self):
        """AC-9: no Python needed to add a model."""
        self.skipTest("not implemented")
