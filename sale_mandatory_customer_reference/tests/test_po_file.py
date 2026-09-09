"""
Standalone test for fr_CA.po file correctness.

Acceptance criteria:
- The file is valid UTF-8.
- The file contains exactly 8 non-empty translation entries (msgid + msgstr pairs).
- Each of the 8 expected msgids is present and has a non-empty msgstr.
- No expected msgstr is identical to its msgid (i.e. actually translated),
  except for intentional language-neutral abbreviations listed in
  LANGUAGE_NEUTRAL_MSGIDS.

This test does NOT require an Odoo runtime.  Run it with:
    python3 -m pytest sale_mandatory_customer_reference/tests/test_po_file.py -v
or from the repo root:
    python3 -m unittest sale_mandatory_customer_reference.tests.test_po_file
"""

import os
import re
import unittest


PO_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "i18n",
    "fr_CA.po",
)

# (msgid, expected_msgstr) pairs — must all be present and non-empty
EXPECTED_TRANSLATIONS = [
    (
        "Your Reference",
        "Votre référence",
    ),
    (
        "# PO",
        "# PO",
    ),
    (
        "Enter your purchase order number",
        "Entrez votre numéro de bon de commande",
    ),
    (
        "A reference (PO number) is required before confirming this order.",
        "Une référence (numéro de bon de commande) est requise avant de confirmer cette commande.",
    ),
    (
        "Reference updated successfully",
        "Référence mise à jour avec succès",
    ),
    (
        "Could not determine the order ID",
        "Impossible de déterminer l'identifiant de la commande",
    ),
    (
        "Failed to save your reference. Please try again.",
        "Échec de l'enregistrement de votre référence. Veuillez réessayer.",
    ),
    (
        "Customer reference (PO Number) is required before confirming this order. "
        "Please set the customer reference field.",
        "Une référence client (numéro de bon de commande) est requise avant de confirmer"
        " cette commande. Veuillez renseigner le champ de référence client.",
    ),
]

# msgids whose msgstr is intentionally identical to the msgid (language-neutral
# abbreviations or symbols that do not require translation).
LANGUAGE_NEUTRAL_MSGIDS = {"# PO"}


def _parse_po(path):
    """
    Minimal PO parser: returns a dict mapping msgid -> msgstr.
    Handles single-line and multi-line quoted strings.
    Skips the header entry (empty-string msgid).
    """
    with open(path, encoding="utf-8") as fh:
        content = fh.read()

    # Split on blank lines to get individual entries
    entries = re.split(r"\n\n+", content.strip())

    result = {}
    for entry in entries:
        # Skip comment-only blocks
        if not re.search(r"^msgid\s+", entry, re.MULTILINE):
            continue

        msgid = _extract_value(entry, "msgid")
        msgstr = _extract_value(entry, "msgstr")

        # Skip the PO header entry
        if msgid == "":
            continue

        result[msgid] = msgstr

    return result


def _extract_value(entry, keyword):
    """
    Extract the string value for a keyword (msgid or msgstr) from a PO entry.
    Handles continuation lines (lines that start with a quoted string after the
    keyword line).
    """
    pattern = re.compile(
        r'^' + keyword + r'\s+"((?:[^"\\]|\\.)*)"\s*$',
        re.MULTILINE,
    )
    continuation = re.compile(r'^\s*"((?:[^"\\]|\\.)*)"', re.MULTILINE)

    match = pattern.search(entry)
    if not match:
        return ""

    value = match.group(1)
    # Collect any continuation lines that follow
    rest = entry[match.end():]
    for line in rest.splitlines():
        m = continuation.match(line)
        if m:
            value += m.group(1)
        else:
            break

    # Unescape basic PO escape sequences
    value = value.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
    return value


class TestFrCaPoFile(unittest.TestCase):
    """Tests that fr_CA.po is well-formed and contains the expected translations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.po_path = os.path.abspath(PO_PATH)
        cls.translations = _parse_po(cls.po_path)

    def test_file_exists(self):
        """The fr_CA.po file must exist at the expected path."""
        self.assertTrue(
            os.path.isfile(self.po_path),
            f"fr_CA.po not found at {self.po_path}",
        )

    def test_file_is_valid_utf8(self):
        """The file must be readable as valid UTF-8."""
        with open(self.po_path, "rb") as fh:
            raw = fh.read()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            self.fail(f"fr_CA.po is not valid UTF-8: {exc}")

    def test_entry_count(self):
        """There must be exactly 8 non-header translation entries."""
        self.assertEqual(
            len(self.translations),
            8,
            f"Expected 8 translation entries, found {len(self.translations)}: "
            f"{list(self.translations.keys())}",
        )

    def test_all_msgids_present(self):
        """Every expected msgid must be present in the file."""
        for msgid, _msgstr in EXPECTED_TRANSLATIONS:
            with self.subTest(msgid=msgid):
                self.assertIn(
                    msgid,
                    self.translations,
                    f"msgid not found in fr_CA.po: {msgid!r}",
                )

    def test_all_msgstr_non_empty(self):
        """Every expected msgid must have a non-empty msgstr."""
        for msgid, _msgstr in EXPECTED_TRANSLATIONS:
            with self.subTest(msgid=msgid):
                msgstr = self.translations.get(msgid, "")
                self.assertTrue(
                    msgstr.strip(),
                    f"Empty msgstr for msgid: {msgid!r}",
                )

    def test_all_msgstr_values_match(self):
        """Every msgstr must exactly match the design-specified translation."""
        for msgid, expected_msgstr in EXPECTED_TRANSLATIONS:
            with self.subTest(msgid=msgid):
                actual = self.translations.get(msgid, "")
                self.assertEqual(
                    actual,
                    expected_msgstr,
                    f"msgstr mismatch for msgid {msgid!r}:\n"
                    f"  expected: {expected_msgstr!r}\n"
                    f"  actual:   {actual!r}",
                )

    def test_no_untranslated_strings(self):
        """
        No msgstr must be identical to its msgid (would mean untranslated),
        except for msgids listed in LANGUAGE_NEUTRAL_MSGIDS (abbreviations that
        are intentionally the same across languages, e.g. "# PO").
        """
        for msgid, _msgstr in EXPECTED_TRANSLATIONS:
            if msgid in LANGUAGE_NEUTRAL_MSGIDS:
                continue
            with self.subTest(msgid=msgid):
                actual = self.translations.get(msgid, "")
                self.assertNotEqual(
                    actual,
                    msgid,
                    f"msgstr is identical to msgid (untranslated): {msgid!r}",
                )
