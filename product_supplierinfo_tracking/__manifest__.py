# -*- coding: utf-8 -*-

{
    "name": "Product Supplierinfo Tracking",
    "version": "19.0.3.0.1",
    "license": "LGPL-3",
    "author": "Bemade",
    "category": "Tools",
    "depends": [
        "base",
        "product",
        "stock",
        "sale",
        "purchase",
        "mrp",
    ],
    "external_dependencies": {"python": ["markupsafe"]},
    "description": """
    This module extends basic inventory support for supplierinfo chatter making price 
    updates visible in the chatter.
    """,
    "demo": [],
    'data': [
        'views/product_view.xml',
        'views/supplierinfo.xml',
    ],
    'test': [],
    'installable': True,
    'active': False
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
