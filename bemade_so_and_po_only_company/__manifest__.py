# -*- coding: utf-8 -*-
{
    "name": "Force Partner to be a company on SO and PO",
    "version": "17.0.0.0.1",
    "category": "Extra Tools",
    'summary': 'Force Partner to be a company on SO and PO',
    "description": """
    Force Partner to be a company on SO and PO
    """,
    "author": "Bemade",
    'website': 'https://www.bemade.org',
    "depends": [
        'purchase',
        'stock',
        'sale',
    ],
    "data": [
        'views/sale_order.xml',
        'views/purchase_order.xml',
    ],
    "auto_install": False,
    "installable": True,
    'license': 'OPL-1'
}
