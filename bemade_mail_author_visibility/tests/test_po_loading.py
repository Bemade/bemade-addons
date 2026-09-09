# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
#
# Acceptance criteria tested here
# --------------------------------
# 9. PO loading — both i18n/fr_CA.po and i18n/bemade_mail_author_visibility.pot
#    parse without any ERROR log from odoo.tools.translate, and the reader
#    yields at least one entry with type == 'model_terms', imd_model ==
#    'ir.ui.view', name == 'ir.ui.view,arch_db', imd_name in
#    {'mail_notification_layout', 'mail_notification_light'}, and source
#    '<strong>Posted by:</strong>'.

import os

from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import TranslationFileReader


def _i18n_dir():
    """Return the absolute path to bemade_mail_author_visibility/i18n/."""
    here = os.path.dirname(__file__)  # …/tests/
    return os.path.join(here, "..", "i18n")


@tagged("post_install", "-at_install", "bemade_mail_author_visibility")
class TestPoLoading(TransactionCase):
    """Test that the fr_CA .po and .pot files load cleanly via TranslationFileReader."""

    def _assert_clean_load(self, po_path):
        """Parse *po_path* and assert no ERROR logs; return list of yielded dicts."""
        entries = []
        with self.assertNoLogs("odoo.tools.translate", level="ERROR"):
            for entry in TranslationFileReader(po_path, fileformat="po"):
                entries.append(entry)
        return entries

    def _find_posted_by_entry(self, entries):
        """Return all entries whose source is the canonical 'Posted by:' msgid."""
        return [
            e for e in entries
            if e.get("src") == "<strong>Posted by:</strong>"
        ]

    def test_09_po_loads_without_malformed_warning(self):
        """fr_CA.po and .pot parse cleanly and yield the expected arch_db entries."""
        i18n = _i18n_dir()
        fr_ca_path = os.path.join(i18n, "fr_CA.po")
        pot_path = os.path.join(i18n, "bemade_mail_author_visibility.pot")

        for label, path in [("fr_CA.po", fr_ca_path), (".pot", pot_path)]:
            with self.subTest(file=label):
                entries = self._assert_clean_load(path)
                posted_by = self._find_posted_by_entry(entries)
                self.assertTrue(
                    posted_by,
                    f"{label}: expected at least one entry with "
                    "src='<strong>Posted by:</strong>'",
                )
                matched_xmlids = {e["imd_name"] for e in posted_by}
                expected_xmlids = {"mail_notification_layout", "mail_notification_light"}
                self.assertTrue(
                    matched_xmlids & expected_xmlids,
                    f"{label}: expected imd_name in {expected_xmlids!r}, "
                    f"got {matched_xmlids!r}",
                )
                for entry in posted_by:
                    if entry["imd_name"] not in expected_xmlids:
                        continue
                    with self.subTest(imd_name=entry["imd_name"]):
                        self.assertEqual(
                            entry["type"],
                            "model_terms",
                            f"{label}: expected type='model_terms', "
                            f"got {entry['type']!r}",
                        )
                        self.assertEqual(
                            entry["imd_model"],
                            "ir.ui.view",
                            f"{label}: expected imd_model='ir.ui.view', "
                            f"got {entry['imd_model']!r}",
                        )
                        self.assertEqual(
                            entry["name"],
                            "ir.ui.view,arch_db",
                            f"{label}: expected name='ir.ui.view,arch_db', "
                            f"got {entry['name']!r}",
                        )
