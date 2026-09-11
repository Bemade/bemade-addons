"""The round-trip invariant.

ACCEPTANCE CRITERIA
===================

This is the governing property of the module. Everything else is a detail of
how it is achieved.

    read(instance)            -> document
    write(document, fresh)    -> fresh instance configured
    read(fresh)               -> the SAME document

A domain that does not round-trip has a missing or lossy handler. Stating it as
an invariant makes new handlers provably complete rather than complete by
inspection, and it catches the failure mode that actually bites: a setting that
is applied but never read back, so a later export silently drops it and nobody
notices until a rebuild.

AC-1  Reading an instance produces a document that validates against the
      schema.

AC-2  Writing that document to a second, freshly initialised database and
      reading it back produces a document EQUAL to the first. Equality is
      semantic (parsed structures compare equal), not textual -- key order and
      formatting are not part of the contract.

AC-3  Writing a document to an instance that already matches it changes
      NOTHING: the change report is empty and no write query is issued for a
      value already correct.

AC-4  Writing twice in succession is identical to writing once. Idempotence is
      asserted on the second write producing an empty change report, not merely
      on it "not raising".

AC-5  Secrets round-trip as their REFERENCE. Reading an instance whose mail
      server has a password emits `!secret <path>`, never the value. The
      resolved value appears nowhere in the emitted document.

AC-6  Derived configuration round-trips as the FACT, not the derivation. An
      instance whose taxes match the matrix derived from `tax_registrations`
      reads back as those registrations with no explicit overrides; one that
      deviates reads back with overrides for exactly the entries that differ.
      (Requires instance_config_account; skipped without it.)

AC-7  A domain with no handler is REPORTED, not silently skipped. Reading an
      instance that has configuration the module cannot express produces a
      warning naming the models, so the gap is visible rather than discovered
      later as a missing setting.

AC-8  Dry run produces the same change report as a real write and writes
      nothing. Asserted by dry-running against a divergent instance, confirming
      a non-empty report, then confirming the instance is unchanged.

AC-9  A write that fails partway leaves the instance unchanged -- the whole
      apply is one transaction.

      LIMITATION, stated rather than discovered later: atomicity cannot span
      the MODULE boundary. Module changes are marked in this transaction but
      carried out by the next registry update (Odoo forbids in-process
      install during init and inside tests -- see tools/modules.py), so they
      cannot be rolled back here. Module state is a separate, re-runnable
      phase; everything else is one savepoint.

AC-10 A fresh-database round trip (read A -> write to empty B -> read B) is
      the real proof and cannot run inside the standard suite: it needs a
      second database and real module installs. It lives outside, tagged
      -standard, the way odoo_herd tags its cluster-dependent tests. What CAN
      be asserted here is stability on one instance: read -> write back ->
      read produces the same document and an empty change report.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..tools import engine
from ..tools.secrets import SecretRef
from .common import InstanceConfigCase


@tagged("post_install", "-at_install")
class TestRoundTrip(InstanceConfigCase):

    def test_read_produces_valid_document(self):
        """AC-1: versioned, and every section belongs to a handler."""
        document, _report = engine.read(self.env)
        self.assertEqual(document["version"], engine.SCHEMA_VERSION)
        domains = {h.domain for h in engine.all_handlers(self.env)}
        for key in document:
            if key not in engine.META_KEYS:
                self.assertIn(key, domains)

    def test_read_write_read_is_stable(self):
        """AC-2 / AC-10: on one instance, read -> write back -> read is fixed."""
        first, _r = engine.read(self.env)
        engine.write(self.env, first)
        second, _r = engine.read(self.env)
        self.assertEqual(first, second)

    def test_write_of_matching_document_is_a_noop(self):
        """AC-3 / AC-4: re-applying an instance's own config changes nothing."""
        document, _r = engine.read(self.env)
        report = engine.write(self.env, document)
        self.assertTrue(
            report.empty,
            "re-applying an instance's own configuration reported changes: %s"
            % report.changes,
        )

    def test_secrets_round_trip_as_references(self):
        """AC-5: the resolved value appears nowhere in the document."""
        self.env["ir.mail_server"].create({
            "name": "rt-secret", "smtp_host": "smtp.example.test",
            "smtp_pass": "hunter2",
        })
        document, _r = engine.read(self.env)
        entry = next(
            e for e in document["ir.mail_server"] if e["name"] == "rt-secret")
        self.assertIsInstance(entry["smtp_pass"], SecretRef)
        self.assertNotIn("hunter2", repr(document))

    def test_unhandled_section_is_reported(self):
        """AC-7: a gap is visible, never a silent skip."""
        document, _r = engine.read(self.env)
        document["some.model.nobody.handles"] = [{"name": "x"}]
        report = engine.write(self.env, document)
        self.assertIn("some.model.nobody.handles", str(report.unhandled))

    def test_dry_run_reports_without_writing(self):
        """AC-8."""
        server = self.env["ir.mail_server"].create({
            "name": "rt-dry", "smtp_host": "before.example.test"})
        document, _r = engine.read(self.env)
        entry = next(
            e for e in document["ir.mail_server"] if e["name"] == "rt-dry")
        entry["smtp_host"] = "after.example.test"
        report = engine.write(self.env, document, dry_run=True)
        self.assertFalse(report.empty, "dry run must still report the change")
        self.assertEqual(server.smtp_host, "before.example.test")

    def test_dry_run_leaves_no_trace_in_the_cache(self):
        """A dry run must not change what the NEXT read sees.

        The savepoint rollback clears the ORM record cache (cr.clear()) but
        not the registry caches. Implied groups derive from
        res.groups' ormcache('groups'): the apply clears it mid-run, later
        reads repopulate it with the post-write graph, and the rollback leaves
        that in place. Two consecutive dry runs of the same divergent document
        must report the same changes -- the second used to report nothing,
        because the stale cache said the implied group was already there.

        Uses group_multi_currency, which base_setup provides, so the test runs
        on the minimal database and does not skip its way to green.
        """
        settings = self.env["res.config.settings"]
        self.assertIn("group_multi_currency", settings._fields)
        settings.create({"group_multi_currency": False}).execute()
        implied = self.env.ref("base.group_multi_currency")
        base_user = self.env.ref("base.group_user")
        # The users section matters: writing group_ids AFTER the settings
        # write reads the group graph, which repopulates the registry cache
        # with the post-write state. Without it the stale cache is never
        # built and the bug does not show.
        document = {"version": 1,
                    "settings": {"group_multi_currency": True},
                    "ir.mail_server": [{"name": "rt-cache",
                                        "smtp_host": "h.example.test"}],
                    "res.users": [{"login": "rt-cache-user", "name": "RT",
                                   "group_ids": ["base.group_user"]}]}
        first = engine.write(self.env, document, dry_run=True)
        second = engine.write(self.env, document, dry_run=True)
        self.assertFalse(first.empty)
        self.assertEqual(
            [c.key for c in first.changes], [c.key for c in second.changes])
        self.assertNotIn(implied, base_user.all_implied_ids)
        self.assertFalse(
            self.env["ir.mail_server"].search([("name", "=", "rt-cache")]))

    def test_failed_write_is_atomic(self):
        """AC-9: a failure partway leaves everything as it was."""
        server = self.env["ir.mail_server"].create({
            "name": "rt-atomic", "smtp_host": "before.example.test"})
        document, _r = engine.read(self.env)
        entry = next(
            e for e in document["ir.mail_server"] if e["name"] == "rt-atomic")
        entry["smtp_host"] = "after.example.test"
        # A user entry with no natural key is refused by the users handler,
        # which runs AFTER mail servers -- so the mail change must roll back.
        document["res.users"] = [{"name": "no-login"}]
        with self.assertRaises(UserError):
            engine.write(self.env, document)
        self.assertEqual(server.smtp_host, "before.example.test")

    def test_unresolvable_secret_on_fresh_record_is_fatal(self):
        """AC-4 of secrets, at engine level.

        No source and no existing value to keep -> hard error, and the
        savepoint means nothing else from the document landed either.
        """
        document, _r = engine.read(self.env)
        document.pop("secrets", None)
        document["ir.mail_server"] = [{
            "name": "rt-nosrc", "smtp_host": "x.example.test",
            "smtp_pass": SecretRef("mail.nosrc"),
        }]
        with self.assertRaises(UserError):
            engine.write(self.env, document)
        self.assertFalse(
            self.env["ir.mail_server"].search([("name", "=", "rt-nosrc")]))

    def test_unresolvable_secret_on_existing_record_keeps_its_value(self):
        """Re-applying an instance's own config must not demand a secrets file
        for credentials that are already in place."""
        server = self.env["ir.mail_server"].create({
            "name": "rt-keep", "smtp_host": "smtp.example.test",
            "smtp_pass": "already-there",
        })
        document, _r = engine.read(self.env)
        report = engine.write(self.env, document)      # no secrets.source
        self.assertEqual(server.smtp_pass, "already-there")
        self.assertIn(
            "rt-keep.smtp_pass",
            [k for _d, k, _rule in report.skipped])

    def test_wrong_version_is_refused(self):
        with self.assertRaises(UserError):
            engine.write(self.env, {"version": 99})
