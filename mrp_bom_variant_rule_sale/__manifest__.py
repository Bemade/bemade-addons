#
#    Bemade Inc.
#
#    Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    License: LGPL-3
#
{
    "name": "BOM generation from variant attribute rules - Sales",
    "version": "18.0.1.0.0",
    "summary": "Generate and price configured variants from the quotation",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "category": "Sales/Sales",
    "license": "LGPL-3",
    "depends": [
        "mrp_bom_variant_rule",
        "sale",
    ],
    "data": [
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "auto_install": True,
}
