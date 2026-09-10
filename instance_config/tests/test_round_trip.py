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
"""

from .common import InstanceConfigCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestRoundTrip(InstanceConfigCase):

    def test_read_produces_valid_document(self):
        """AC-1."""
        self.skipTest("not implemented")

    def test_read_write_read_is_stable(self):
        """AC-2: the invariant."""
        self.skipTest("not implemented")

    def test_write_of_matching_document_is_a_noop(self):
        """AC-3: empty change report, no writes."""
        self.skipTest("not implemented")

    def test_second_write_reports_no_changes(self):
        """AC-4: idempotence asserted on the report, not on not-raising."""
        self.skipTest("not implemented")

    def test_secrets_round_trip_as_references(self):
        """AC-5: resolved values appear nowhere in the document."""
        self.skipTest("not implemented")

    def test_unhandled_domains_are_reported(self):
        """AC-7: gaps are visible, never silent."""
        self.skipTest("not implemented")

    def test_dry_run_reports_without_writing(self):
        """AC-8."""
        self.skipTest("not implemented")

    def test_failed_write_is_atomic(self):
        """AC-9."""
        self.skipTest("not implemented")
