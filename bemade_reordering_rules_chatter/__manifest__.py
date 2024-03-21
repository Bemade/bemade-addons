# -*- coding: utf-8 -*-
{
    "name": "Chatter on the Reordering Rules",
    "version": "17.0.0.0.1",
    "category": "Extra Tools",
    'license': 'GPL-3',
    'summary': 'Add chatter on the reordering rules',
    "description": """
    Add chatter on the reordering rules
    """,
    "author": "Bemade",
    'website': 'https://www.bemade.org',
    "depends": [
        'stock',
    ],
    "data": [
        # BV : FOR MIGRATION
        'views/stock_warehouse_orderpoint.xml',
    ],
    "auto_install": False,
    "installable": True,
}
