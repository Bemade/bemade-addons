"""The readable layer.

ACCEPTANCE CRITERIA
===================

AC-1  A readable document and its canonical twin apply IDENTICALLY. This is
      the whole contract: aliases change how a document reads, never what it
      does.
AC-2  to_readable(to_canonical(doc)) == doc for any document using only
      aliased names, and to_canonical(to_readable(doc)) == doc for any
      canonical one. The two are inverses.
AC-3  A name with no alias passes through unchanged in both directions.
      Nothing is un-exportable for lack of a pretty name.
AC-4  `rights:` bundles expand into groups on every user naming one, so "same
      rights as X" is stated once. A bundle that is named but not defined is
      a clear error, not a KeyError.
AC-5  `features:` naming a feature with no known setting behind it is a clear
      error -- a typo must not vanish silently.
AC-6  A readable export of a live instance is itself a valid document that
      applies back with an empty change report.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..tools import engine
from ..tools.aliases import to_canonical, to_readable
from .common import InstanceConfigCase


@tagged("post_install", "-at_install")
class TestAliases(InstanceConfigCase):

    READABLE = {
        "version": 1,
        "companies": [{"name": "Alias Co", "currency": "CAD", "country": "CA"}],
        "mail": {
            "outgoing": [{"name": "alias-smtp", "host": "smtp.example.test",
                          "port": 587, "encryption": "starttls"}],
        },
        "rights": {"clerk": ["base.group_user"]},
        "users": [{"login": "alias-user", "name": "Alias User",
                   "rights": "clerk", "companies": ["Alias Co"],
                   "default_company": "Alias Co"}],
        "features": {"analytic_accounting": True},
    }

    def test_canonical_form_is_what_handlers_expect(self):
        doc = to_canonical(self.READABLE)
        self.assertIn("res.company", doc)
        self.assertEqual(doc["res.company"][0]["currency_id"], "CAD")
        self.assertEqual(doc["ir.mail_server"][0]["smtp_host"], "smtp.example.test")
        self.assertEqual(doc["res.users"][0]["group_ids"], ["base.group_user"])
        self.assertEqual(doc["settings"], {"group_analytic_accounting": True})
        self.assertNotIn("rights", doc)
        self.assertNotIn("features", doc)
        self.assertNotIn("mail", doc)

    def test_readable_and_canonical_apply_identically(self):
        """AC-1: the whole contract."""
        readable = self.READABLE
        canonical = to_canonical(readable)
        r1 = engine.write(self.env, readable, dry_run=True)
        r2 = engine.write(self.env, canonical, dry_run=True)
        self.assertEqual(r1.changes, r2.changes)
        self.assertEqual(r1.unhandled, r2.unhandled)

    def test_alias_layers_are_inverses(self):
        """AC-2."""
        canonical = to_canonical(self.READABLE)
        again = to_canonical(to_readable(canonical))
        self.assertEqual(again, canonical)

    def test_unaliased_names_pass_through(self):
        """AC-3."""
        doc = {"version": 1, "res.currency": [{"name": "XYZ"}],
               "settings": {"some_unaliased_setting": 1}}
        self.assertEqual(to_canonical(doc), doc)
        self.assertEqual(
            to_readable(doc)["settings"], {"some_unaliased_setting": 1})

    def test_undefined_rights_bundle_is_a_clear_error(self):
        """AC-4."""
        doc = {"version": 1, "users": [{"login": "x", "rights": "nope"}]}
        with self.assertRaises(UserError) as caught:
            to_canonical(doc)
        self.assertIn("nope", str(caught.exception))

    def test_unknown_feature_is_a_clear_error(self):
        """AC-5: a typo must not vanish."""
        with self.assertRaises(UserError) as caught:
            to_canonical({"version": 1, "features": {"analitic": True}})
        self.assertIn("analitic", str(caught.exception))

    def test_readable_export_applies_back_cleanly(self):
        """AC-6: the export is a real document, not just pretty output."""
        readable, _r = engine.read(self.env, readable=True)
        self.assertIn("companies", readable)
        report = engine.write(self.env, readable)
        self.assertTrue(
            report.empty,
            "readable export re-applied with changes: %s" % report.changes)
