"""Secret resolution.

ACCEPTANCE CRITERIA
===================

The configuration file must be safe to commit, diff and review, so it carries
no credential -- only references::

    password: !secret mail.outgoing.primary

resolved at load time against the source named by ``secrets.source``.

AC-1  ``file:<path>`` resolves a dotted path against a mounted YAML file.
AC-2  ``env:PREFIX_`` resolves against environment variables, dots uppercased
      to underscores.
AC-3  An UNRESOLVABLE reference is a hard error naming the path -- when there
      is nothing to fall back on. Never a silent blank: a blank password
      produces an instance that looks configured and does not work.

      Refinement, from the round-trip suite: if the record already EXISTS and
      already HOLDS a value, an unresolvable reference keeps that value and is
      reported as skipped. Re-applying an instance's own configuration must not
      demand a secrets file for credentials already in place. A fresh record,
      or an empty field, is the fatal case.
AC-4  A missing secrets SOURCE, when the document contains a reference, is a
      hard error -- not mistaken for "no secrets needed".
AC-5  A resolved secret never reaches a log or an exception message.
AC-6  Documents emit references, never values.
AC-7  An explicit null is DISTINCT from a missing secret: legitimately no
      value, record created without one. Real instances have users in this
      state: invited but never activated, so there is no hash to carry.
AC-8  A path that exists but holds an empty string is unresolvable (AC-3), not
      a valid empty password.
AC-9  Resolution is lazy -- a reference in a section not being applied need
      not resolve.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..tools.secrets import (
    SecretRef, SecretSource, dump_document, load_document,
)
from .common import InstanceConfigCase


@tagged("post_install", "-at_install")
class TestSecrets(InstanceConfigCase):

    def test_file_source_resolves_dotted_path(self):
        """AC-1."""
        spec = self.secrets_file({"mail": {"outgoing": {"primary": "s3cr3t"}}})
        source = SecretSource.from_spec(spec)
        self.assertEqual(
            source.resolve(SecretRef("mail.outgoing.primary")), "s3cr3t")

    def test_env_source_resolves_with_prefix(self):
        """AC-2: dots uppercased to underscores."""
        source = SecretSource.from_spec("env:CFG_")
        with self.patched_environ(CFG_MAIL_OUTGOING_PRIMARY="from-env"):
            self.assertEqual(
                source.resolve(SecretRef("mail.outgoing.primary")), "from-env")

    def test_unresolvable_reference_raises(self):
        """AC-3: names the path, never substitutes a blank."""
        spec = self.secrets_file({"mail": {}})
        source = SecretSource.from_spec(spec)
        with self.assertRaises(UserError) as caught:
            source.resolve(SecretRef("mail.outgoing.primary"))
        self.assertIn("mail.outgoing.primary", str(caught.exception))

    def test_empty_value_is_unresolvable(self):
        """AC-8: an empty credential is never intentional."""
        spec = self.secrets_file({"mail": {"outgoing": {"primary": ""}}})
        source = SecretSource.from_spec(spec)
        with self.assertRaises(UserError):
            source.resolve(SecretRef("mail.outgoing.primary"))

    def test_missing_source_yields_no_resolver(self):
        """AC-4: absent source is distinguishable from a usable one."""
        self.assertIsNone(SecretSource.from_spec(None))
        self.assertIsNone(SecretSource.from_spec(""))

    def test_unknown_scheme_raises(self):
        """AC-4: a typo'd scheme fails loudly rather than silently."""
        with self.assertRaises(UserError):
            SecretSource.from_spec("vault:/some/path")

    def test_secret_never_appears_in_repr_or_errors(self):
        """AC-5: SecretRef holds a path, never a value."""
        spec = self.secrets_file({"mail": {"outgoing": {"primary": "s3cr3t"}}})
        source = SecretSource.from_spec(spec)
        ref = SecretRef("mail.outgoing.primary")
        source.resolve(ref)
        self.assertNotIn("s3cr3t", repr(ref))
        with self.assertRaises(UserError) as caught:
            source.resolve(SecretRef("mail.outgoing.absent"))
        self.assertNotIn("s3cr3t", str(caught.exception))

    def test_document_round_trips_references_not_values(self):
        """AC-6: load -> dump -> load preserves the reference.

        Compared semantically, not textually: the round-trip contract is on
        parsed structures, and PyYAML may legitimately quote the scalar
        (`!secret 'mail.outgoing.primary'`). Asserting on raw text would make
        this test fail on a formatting choice that changes nothing.
        """
        text = "mail:\n  password: !secret mail.outgoing.primary\n"
        data = load_document(text)
        self.assertEqual(data["mail"]["password"],
                         SecretRef("mail.outgoing.primary"))
        emitted = dump_document(data)
        self.assertIn("!secret", emitted)
        self.assertNotIn("s3cr3t", emitted)
        self.assertEqual(load_document(emitted), data)

    def test_explicit_null_is_not_a_secret_reference(self):
        """AC-7: `password_hash: ~` means legitimately no value."""
        data = load_document("users:\n  - password_hash: ~\n")
        self.assertIsNone(data["users"][0]["password_hash"])
        self.assertNotIsInstance(data["users"][0]["password_hash"], SecretRef)

    def test_resolution_is_lazy(self):
        """AC-9: loading a document resolves nothing on its own."""
        spec = self.secrets_file({})
        SecretSource.from_spec(spec)          # never consulted
        data = load_document("a: !secret x.y\n")
        self.assertIsInstance(data["a"], SecretRef)
