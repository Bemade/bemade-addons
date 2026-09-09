#
#    Bemade Inc.
#
#    Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    License: LGPL-3
#
{
    "name": "Pricelist prices based on BOM cost",
    "version": "18.0.1.0.0",
    "summary": "Add a pricelist-item base option that prices off the product's BOM cost",
    "description": """Pricelist prices based on BOM cost
==================================

Adds a new ``base`` option (*Prices based on BOM cost*) to pricelist items,
structurally parallel to OCA ``product_pricelist_supplierinfo``'s
``base="supplierinfo"``. When a formula-type pricelist item uses this base, the
unit price is computed from the product's **BOM cost rollup** (components +
operations, via ``mrp_account``) instead of the list price or the vendor price,
with the pricelist rule's formula margin/discount/surcharge applied on top.

Intended for make-or-buy products: a BOM-cost pricelist rule prices the line
off what it costs to *manufacture* the product, in the same way
``product_pricelist_supplierinfo`` prices off what it costs to *buy* it.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "category": "Sales/Sales",
    "license": "LGPL-3",
    "depends": [
        "product",
        "mrp_account",
    ],
    "data": [],
    "installable": True,
    "auto_install": False,
}
