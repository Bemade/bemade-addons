# -*- coding: utf-8 -*-
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
# Copyright (C) 2026 Bemade Inc., Marc Durepos <marc@bemade.org>
"""Integration tests for the ir.actions.report record.

Acceptance criteria
-------------------
1. After install, the record
   customer_account_statement.action_report_customer_account_statement
   has print_report_name == "object._account_statement_filename()".
2. Evaluating that expression via safe_eval with object = a freshly created
   partner returns the same string as partner._account_statement_filename().
"""
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval


class TestReportAction(TransactionCase):

    def _get_action(self):
        return self.env.ref(
            "customer_account_statement.action_report_customer_account_statement"
        )

    # --- AC1: print_report_name field set correctly ---
    def test_print_report_name_field(self):
        action = self._get_action()
        self.assertEqual(
            action.print_report_name,
            "object._account_statement_filename()",
        )

    # --- AC2: safe_eval resolves to helper result ---
    def test_safe_eval_resolves_to_helper(self):
        action = self._get_action()
        partner = self.env["res.partner"].create(
            {"name": "Test Client SA", "is_company": True}
        )
        expr = action.print_report_name
        evaluated = safe_eval(expr, {"object": partner})
        expected = partner._account_statement_filename()
        self.assertEqual(evaluated, expected)
