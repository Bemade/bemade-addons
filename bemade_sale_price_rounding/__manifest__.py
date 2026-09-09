# -*- coding: utf-8 -*-
{
    "name": "Bemade Sale Price Rounding",
    "version": "18.0.2.0.0",
    "category": "Sales",
    "summary": (
        "Round sale order line unit prices and cost to Product Price precision "
        "after pricelist computation"
    ),
    "description": """
Rounds the unit price and cost (purchase price) on sale order lines to the
``Product Price`` decimal precision after pricelist computation, preventing
extra trailing decimals from appearing on customer-facing and internal documents.

**Bug 1 — Unit price total inconsistency (fixed since 18.0.1.0.0)**

Since Odoo 18, price fields use a minimum display precision rather than a
hard precision, meaning pricelist percentage/formula rules can produce unit
prices with 4–6 decimal places.  This causes customer-facing documents to
show inconsistent math (e.g. ``288.48 × 3 = 865.44`` displayed, but
``price_subtotal`` computed from the raw ``288.480769``).  This module
rounds ``price_unit`` (and ``technical_price_unit``) in the ORM cache
*before* ``_compute_amount`` runs.

**Bug 2 — PDF cost column shows extra decimals on quotes (fixed since 18.0.2.0.0)**

``sale.order.line.purchase_price`` (declared by ``sale_margin`` with
``min_display_digits``, which is display-only) stores the raw unrounded
float in the database.  On confirmed SOs a downstream recompute from
``sale_stock_margin`` happens to round the value via an average-cost
calculation, so confirmed documents look fine.  On draft/sent quotes the
stored value leaks 3–14 trailing decimals into PDF templates.  This module
re-declares the field with ``digits="Product Price"`` and rounds the value
in cache at compute time (``_compute_purchase_price``) and at direct
write/create time.
    """,
    "author": "Bemade Inc., Marc Durepos <marc@bemade.org>",
    "website": "https://www.bemade.org",
    "depends": ["sale", "sale_margin"],
    "auto_install": False,
    "installable": True,
    "license": "LGPL-3",
}
