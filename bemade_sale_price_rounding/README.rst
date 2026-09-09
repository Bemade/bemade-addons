==========================
Bemade Sale Price Rounding
==========================

Rounds the unit price and cost (``purchase_price``) on sale order lines to the
``Product Price`` decimal precision after pricelist computation, preventing
extra trailing decimals from appearing on customer-facing and internal documents.

Features
--------

**Unit price rounding (Bug 1 — since 18.0.1.0.0)**

Since Odoo 18, price fields use a minimum display precision rather than a
hard precision, meaning pricelist percentage/formula rules can produce unit
prices with 4–6 decimal places.  This causes customer-facing documents to
show inconsistent math (e.g. ``288.48 × 3 = 865.44`` displayed, but
``price_subtotal`` computed from the raw ``288.480769``).  This module
rounds ``price_unit`` (and ``technical_price_unit``) in the ORM cache
*before* ``_compute_amount`` runs, ensuring the subtotal always equals the
displayed unit price times the quantity.

**Cost column rounding (Bug 2 — since 18.0.2.0.0)**

``sale.order.line.purchase_price`` (declared by ``sale_margin`` with
``min_display_digits``, which is display-only) stores the raw unrounded
float in the database.  On confirmed SOs a downstream recompute from
``sale_stock_margin`` happens to round the value via an average-cost
calculation, so confirmed documents look fine.  On draft/sent quotes the
stored value leaks 3–14 trailing decimals into PDF templates (e.g.
``228.09285714285714`` from a UoM conversion of ``4789.95 / 21``).

This module re-declares ``purchase_price`` with ``digits="Product Price"``
and rounds the value in cache at compute time (``_compute_purchase_price``)
and at direct write/create time, fixing the PDF cost column for all states
without touching individual report templates.

Configuration
-------------

No configuration required.  Install alongside ``sale_margin`` (required
dependency).  Decimal precision is read from the ``Product Price`` precision
setting (``Settings → Technical → Database Structure → Decimal Accuracy``).

Usage
-----

- Install the module.
- Create sale orders as usual.  ``price_unit`` and ``purchase_price`` on
  every line will be rounded to ``Product Price`` precision at compute time,
  on direct write, and on create.
- No data migration for historical records is performed; only new writes
  are rounded ("fix forward").

Changelog
---------

18.0.2.0.0 (2026-05-11)
~~~~~~~~~~~~~~~~~~~~~~~~

- **Bug 2 fix**: round ``purchase_price`` at compute/write/create time to
  ``Product Price`` precision, eliminating trailing decimals in the PDF cost
  column on quotes.
- Add ``sale_margin`` as a hard dependency.
- Add regression tests: ``test_price_subtotal_consistency.py`` (Bug 1) and
  ``test_purchase_price_rounding.py`` (Bug 2).

18.0.1.0.0 (2026-04-01)
~~~~~~~~~~~~~~~~~~~~~~~~

- **Bug 1 fix**: round ``price_unit`` and ``technical_price_unit`` in cache
  before ``_compute_amount`` runs, ensuring ``price_subtotal`` equals the
  displayed (rounded) unit price times the quantity.

Credits
-------

- **Author**: Bemade Inc., Marc Durepos <marc@bemade.org>
- **Website**: https://www.bemade.org
- **License**: LGPL-3
