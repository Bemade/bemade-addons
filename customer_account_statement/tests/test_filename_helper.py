# -*- coding: utf-8 -*-
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
# Copyright (C) 2026 Bemade Inc., Marc Durepos <marc@bemade.org>
"""Unit tests for ResPartner._account_statement_filename().

Acceptance criteria
-------------------
1. Plain ASCII commercial_company_name "ACME Inc" →
   "Customer_Account_Statement_ACME_Inc_<today>".
2. Accented FR name "État Métallurgique Côté" →
   "Customer_Account_Statement_Etat_Metallurgique_Cote_<today>".
3. Punctuation/special chars "Côté & Frères, Inc." collapses to only
   [A-Za-z0-9_-], with single underscores between runs and no leading or
   trailing underscore.
4. commercial_company_name empty/false → falls back to name; both
   empty/false → literal "client".
5. Date segment equals fields.Date.context_today(partner).strftime("%Y-%m-%d").
6. Hyphens in the source name (e.g. "Saint-Pierre") survive verbatim — not
   collapsed.
7. Idempotence: calling the helper twice on the same partner returns the
   same string (no hidden state).
"""
import re
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase


class TestFilenameHelper(TransactionCase):

    def _make_partner(self, name=None, company_name=None, is_company=False):
        """Create a partner in memory (rolled back after each test)."""
        vals = {"name": name or "Test Partner"}
        if is_company:
            vals["is_company"] = True
        if company_name is not None:
            # commercial_company_name is a related/computed field; set
            # the parent company to drive it indirectly, or for simplicity
            # set name directly and patch is_company.
            vals["name"] = company_name
            vals["is_company"] = True
        return self.env["res.partner"].create(vals)

    def _today_str(self, partner):
        return fields.Date.context_today(partner).strftime("%Y-%m-%d")

    # --- AC1: plain ASCII ---
    def test_plain_ascii_company_name(self):
        partner = self._make_partner(company_name="ACME Inc")
        result = partner._account_statement_filename()
        today = self._today_str(partner)
        self.assertEqual(result, f"Customer_Account_Statement_ACME_Inc_{today}")

    # --- AC2: accented FR name ---
    def test_accented_name(self):
        partner = self._make_partner(company_name="État Métallurgique Côté")
        result = partner._account_statement_filename()
        today = self._today_str(partner)
        self.assertEqual(
            result,
            f"Customer_Account_Statement_Etat_Metallurgique_Cote_{today}",
        )

    # --- AC3: punctuation collapses ---
    def test_punctuation_collapsed(self):
        partner = self._make_partner(company_name="Côté & Frères, Inc.")
        result = partner._account_statement_filename()
        today = self._today_str(partner)
        # Result must match the safe-slug pattern (no leading/trailing _)
        slug_part = result.removeprefix("Customer_Account_Statement_").removesuffix(f"_{today}")
        self.assertRegex(slug_part, r"^[A-Za-z0-9][A-Za-z0-9_-]*[A-Za-z0-9]$")
        # No consecutive underscores
        self.assertNotIn("__", slug_part)
        # Starts with "Cote" (accent stripped, no leading underscore)
        self.assertTrue(slug_part.startswith("Cote"), slug_part)

    # --- AC4: fallback to name, then to "client" ---
    def test_fallback_to_name(self):
        # Partner with name but no commercial_company_name (not a company,
        # no parent company).
        partner = self.env["res.partner"].create({"name": "Jean Tremblay"})
        result = partner._account_statement_filename()
        today = self._today_str(partner)
        self.assertEqual(
            result, f"Customer_Account_Statement_Jean_Tremblay_{today}"
        )

    def test_fallback_to_client_when_no_name(self):
        # The DB has a check constraint preventing name=NULL on contact-type
        # partners, so we cannot write False to the DB. Instead, patch the
        # ORM property at the Python level to simulate a record with no
        # commercial_company_name and no name, verifying the "client" fallback.
        partner = self.env["res.partner"].create({"name": "placeholder"})
        today = self._today_str(partner)
        with patch.object(type(partner), "commercial_company_name",
                          new_callable=lambda: property(lambda self: False)), \
             patch.object(type(partner), "name",
                          new_callable=lambda: property(lambda self: False)):
            result = partner._account_statement_filename()
        self.assertEqual(
            result, f"Customer_Account_Statement_client_{today}"
        )

    # --- AC5: date segment correctness ---
    def test_date_segment(self):
        partner = self._make_partner(company_name="TestCo")
        today = self._today_str(partner)
        result = partner._account_statement_filename()
        self.assertTrue(result.endswith(f"_{today}"), result)
        # Verify format YYYY-MM-DD
        date_part = result.rsplit("_", 2)[-2] + "-" + result.rsplit("_", 2)[-1]
        # Rebuild: last 10 chars of result
        self.assertRegex(result[-10:], r"\d{4}-\d{2}-\d{2}")

    # --- AC6: hyphens survive ---
    def test_hyphens_survive(self):
        partner = self._make_partner(company_name="Saint-Pierre")
        result = partner._account_statement_filename()
        today = self._today_str(partner)
        self.assertEqual(
            result, f"Customer_Account_Statement_Saint-Pierre_{today}"
        )

    # --- AC7: idempotence ---
    def test_idempotence(self):
        partner = self._make_partner(company_name="ACME Corp")
        first = partner._account_statement_filename()
        second = partner._account_statement_filename()
        self.assertEqual(first, second)
