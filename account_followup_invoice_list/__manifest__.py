{
    "name": "Account Follow-up Invoice List",
    "version": "18.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "Restore inline invoice list in follow-up reminder emails",
    "description": """
Account Follow-up Invoice List
==============================
Odoo 18 removed the table of outstanding invoices from the body of follow-up
reminder emails. The list is now only available as a PDF attachment.

This module restores the inline invoice list so customers can see which
invoices are outstanding directly in the email body, without having to open
the PDF attachment.
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "account_followup",
    ],
    "data": [
        "views/report_followup.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
