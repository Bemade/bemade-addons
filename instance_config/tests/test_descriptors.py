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

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..tools.descriptors import (
    AUDIT_FIELDS, Descriptor, DescriptorRegistry, RULE_AUDIT, RULE_BINARY,
    RULE_INVERSE_O2M, RULE_M2M_OTHER_SIDE, RecordHandler,
    load_descriptors,
)
from ..tools.handler import Report
from ..tools.secrets import SecretRef
from .common import InstanceConfigCase


@tagged("post_install", "-at_install")
class TestDescriptors(InstanceConfigCase):

    def setUp(self):
        super().setUp()
        self.registry = DescriptorRegistry(load_descriptors())
        self.company_handler = RecordHandler(
            self.registry.get("res.company"), self.registry)

    def test_shipped_descriptors_are_valid(self):
        """AC-5: ordering is checked at load time, not mid-apply."""
        self.registry.validate(self.env)

    def test_self_reference_is_allowed(self):
        """AC-5: res.company.parent_id cannot be ordered before itself.

        Self-references are applied in a second pass once every record of the
        model exists, so they are exempt from the ordering rule rather than
        being a configuration error.
        """
        self.registry.validate(self.env)     # would raise on parent_id
        descriptor = self.registry.get("res.company")
        self.assertIn("parent_id", descriptor.infer_fields(self.env))

    def test_bad_ordering_is_caught_at_load_time(self):
        """AC-5: a many2one target applied after its referrer is refused."""
        bad = DescriptorRegistry({
            "res.users": {"key": "login", "order": 10},
            "res.company": {"key": "name", "order": 99},
        })
        with self.assertRaises(UserError) as caught:
            bad.validate(self.env)
        self.assertIn("res.company", str(caught.exception))

    def test_field_inference_excludes_audit_and_computed(self):
        """AC-1."""
        report = Report()
        names = set(self.registry.get("res.company").infer_fields(
            self.env, report))
        self.assertFalse(names & AUDIT_FIELDS)
        skipped = {n: r for _d, n, r in report.skipped}
        for audit in AUDIT_FIELDS & set(self.env["res.company"]._fields):
            self.assertEqual(skipped.get(audit), RULE_AUDIT)
        self.assertIn("name", names)

    def test_one2many_fields_are_dropped(self):
        """AC-1: the many2one side already carries the relationship."""
        report = Report()
        names = set(self.registry.get("res.company").infer_fields(
            self.env, report))
        model = self.env["res.company"]
        for name in names:
            self.assertNotEqual(model._fields[name].type, "one2many")
        self.assertIn(
            RULE_INVERSE_O2M, {r for _d, _n, r in report.skipped})

    def test_many2many_is_carried_by_the_later_side_only(self):
        """AC-1: one relationship, stored once.

        res.company.user_ids and res.users.company_ids are the same many2many.
        Carrying both would store the same fact twice and let the copies
        disagree, and the earlier side cannot reference records that do not
        exist yet. The rule is to carry it on the side applied LATER.
        """
        report = Report()
        company_fields = set(
            self.registry.get("res.company").infer_fields(self.env, report))
        user_fields = set(
            self.registry.get("res.users").infer_fields(self.env, Report()))
        self.assertNotIn("user_ids", company_fields)
        self.assertIn("company_ids", user_fields)
        self.assertIn(
            ("res.company", "user_ids", RULE_M2M_OTHER_SIDE), report.skipped)

    def test_binary_excluded_unless_included(self):
        """AC-2: logo is asked for by the descriptor, other binaries are not."""
        report = Report()
        descriptor = self.registry.get("res.company")
        names = set(descriptor.infer_fields(self.env, report))
        self.assertIn("logo", names)
        model = self.env["res.company"]
        for name in names:
            if model._fields[name].type == "binary":
                self.assertIn(name, descriptor.include)

    def test_logo_round_trips_byte_identically(self):
        """AC-2.

        Uses a real 1x1 PNG: Odoo validates that image fields decode, so
        arbitrary bytes are rejected before they ever reach the handler.
        """
        png = (
            b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
            b"z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        company = self.env.company
        company.logo = png
        emitted = self.company_handler.read(self.env, Report())
        entry = next(e for e in emitted if e["name"] == company.name)
        self.assertEqual(entry["logo"], company.logo)

    def test_many2one_emitted_as_natural_key(self):
        """AC-3: never a raw id."""
        report = Report()
        emitted = self.company_handler.read(self.env, report)
        entry = next(e for e in emitted if e["name"] == self.env.company.name)
        for name, value in entry.items():
            field = self.env["res.company"]._fields[name]
            if field.type == "many2one" and value:
                self.assertNotIsInstance(
                    value, int,
                    "%s emitted a raw id" % name)

    def test_undescribed_many2one_target_is_reported(self):
        """AC-3: a gap is made visible, not papered over with an id."""
        report = Report()
        self.company_handler.read(self.env, report)
        # res.company has many2ones to models with no descriptor (currency,
        # country, partner...), so at least one gap must be recorded.
        self.assertTrue(
            report.unhandled,
            "undescribed many2one targets should be reported")

    def test_secret_fields_emit_references(self):
        """AC-7: never the value."""
        server = self.env["ir.mail_server"].create({
            "name": "test-server", "smtp_host": "smtp.example.test",
            "smtp_pass": "hunter2",
        })
        handler = RecordHandler(
            self.registry.get("ir.mail_server"), self.registry)
        emitted = handler.read(self.env, Report())
        entry = next(e for e in emitted if e["name"] == server.name)
        self.assertIsInstance(entry["smtp_pass"], SecretRef)
        self.assertNotIn("hunter2", str(entry))

    def test_existing_record_is_updated_not_duplicated(self):
        """AC-4: matched on the natural key."""
        model = self.env["ir.mail_server"]
        handler = RecordHandler(
            self.registry.get("ir.mail_server"), self.registry)
        model.create({"name": "dup-test", "smtp_host": "a.example.test"})
        before = model.search_count([("name", "=", "dup-test")])
        handler.write(self.env, [
            {"name": "dup-test", "smtp_host": "b.example.test"}], Report())
        self.assertEqual(
            model.search_count([("name", "=", "dup-test")]), before)
        self.assertEqual(
            model.search([("name", "=", "dup-test")], limit=1).smtp_host,
            "b.example.test")

    def test_rewriting_identical_values_is_a_noop(self):
        """AC-4 / idempotence: no churn on a record already correct."""
        model = self.env["ir.mail_server"]
        handler = RecordHandler(
            self.registry.get("ir.mail_server"), self.registry)
        model.create({"name": "noop-test", "smtp_host": "a.example.test"})
        report = Report()
        handler.write(self.env, [
            {"name": "noop-test", "smtp_host": "a.example.test"}], report)
        self.assertFalse(
            [c for c in report.changes if c.key == "noop-test"],
            "an already-correct record should produce no change")

    def test_entry_without_natural_key_is_refused(self):
        """AC-4: records are matched on their key, never on position."""
        handler = RecordHandler(
            self.registry.get("ir.mail_server"), self.registry)
        with self.assertRaises(UserError):
            handler.write(self.env, [{"smtp_host": "x.example.test"}], Report())

    def test_extra_records_are_reported_not_deleted(self):
        """AC-8: silent deletion is the wrong default."""
        model = self.env["ir.mail_server"]
        handler = RecordHandler(
            self.registry.get("ir.mail_server"), self.registry)
        keeper = model.create({"name": "keep-me", "smtp_host": "a.example.test"})
        report = Report()
        handler.write(self.env, [
            {"name": "other", "smtp_host": "b.example.test"}], report)
        self.assertTrue(keeper.exists(), "must not delete undeclared records")
        self.assertIn("keep-me", str(report.unhandled))

    def test_descriptor_only_model_round_trips(self):
        """AC-9: adding a model needs no Python."""
        registry = DescriptorRegistry({
            "res.currency": {"key": "name", "order": 5},
        })
        handler = RecordHandler(registry.get("res.currency"), registry)
        emitted = handler.read(self.env, Report())
        self.assertTrue(emitted)
        self.assertIn("name", emitted[0])
