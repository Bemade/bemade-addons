# -*- coding: utf-8 -*-
{
    "name": "Customer Account Statement",
    "version": "18.0.1.0.12",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "category": "Accounting/Accounting",
    "depends": [
        "account",
    ],
    "description": """
Customer Account Statement Report
==================================

This module provides a customer account statement report that shows:
- Outstanding invoices for a customer
- Invoice details (date, due date, PO number, amounts)
- Total invoiced, paid, and outstanding amounts

The report can be generated from the partner form view.
    """,
    "data": [
        "report/partner_report.xml",
        "report/report_customer_account_statement.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
