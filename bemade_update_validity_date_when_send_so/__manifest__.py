# -*- coding: utf-8 -*-
{
    "name": "Automatic Quotation Date and Validity Updater",
    "version": "17.0.0.0.1",
    "category": "Extra Tools",
    'summary': 'Automatically updates the sale quotation date and validity date upon sending the quotation',
    "description": """
        This module automatically updates the sale quotation date and its validity date upon sending the quotation. 
        The order date is set to the current date and time, while the validity date is set to 30 days from the current date and time. 
        This ensures your sale quotations always reflect the most accurate and up-to-date information.
    """,
    "author": "Bemade",
    'website': 'https://www.bemade.org',
    "depends": [
        'sale_management'
    ],
    "data": [
    ],
    "auto_install": False,
    "installable": True,
    'license': 'OPL-1'
}