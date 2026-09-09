# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
{
    "name": "Product Cost Source",
    "version": "18.0.1.0.0",
    "summary": "Resolve a product's unit cost, name where it came from, "
    "and say how far it can be trusted.",
    "description": """Product Cost Source
===================

Answering "what does this cost us?" is rarely a single lookup. The number may
come from a vendor pricelist, from the valuation of stock already on hand, or
from what was actually paid the last time the part was purchased -- and when
demand is only partly covered by stock, from more than one of those at once.

This module resolves that question in one place, and reports **which sources it
used and how far each can be relied on**, so that an estimate is never mistaken
for a firm figure.

What it does
------------

Given a product, a quantity, how much of that quantity stock can cover, a
currency and a date, it returns a resolved unit cost together with the evidence
behind it:

* **Vendor pricelist** -- the applicable supplier price, converted to the target
  currency at the given date.
* **Stock valuation** -- the cost of the quantity already on hand.
* **Blended** -- when stock covers part of the demand and a vendor supplies the
  rest, the weighted unit cost of the two.

Alongside the cost, each contributing source is described in terms a person
quoting can act on:

* *Pricing is firm based on a date-bounded vendor pricelist, valid until
  2026-11-30.*
* *Supplier price is more than 6 months old. No transaction since 2022-01-03.*
* *Pricing based on current stock availability and stock valuation.*

How trust is decided
--------------------

A price that falls inside a vendor agreement currently in force is firm
regardless of its age: an eight-month-old price on an annual pricelist is not
stale, because the agreement still binds.

Outside such an agreement there is no contract to lean on, so the age of the
last **known** price is measured against a configurable timeout, and anything
older is reported as an estimate. A purchase is itself a repricing event, so
the last known price is the most recent of a confirmed purchase order line or a
supplier price entry -- not whenever the catalogue record happened to be
written, which on an imported catalogue says more about the import than about
the price.

How often a part is bought does not enter into it. A part bought once every
five years, on a two-year-old price, has an out-of-date price in exactly the
way a monthly part would.

Nothing is ever blocked and no price is ever silently changed. The module
reports what it knows and what it does not, and leaves the decision to the
person quoting.

Extending it
------------

The set of sources is an extension point rather than a fixed list. A module
that knows about another way to establish a cost overrides ``_cost_sources()``
and adds its own; the resolution and reporting above then apply to it
unchanged.

This keeps heavier dependencies out of the core. Purchase-order history, for
instance, arrives through a separate optional module rather than forcing every
installation to carry ``purchase``.

What it is not
--------------

This module has no user-facing screens of its own beyond its settings. It is
the engine other modules build on: bills of material rolling costs up, sales
quotations warning that a price is stale, margin calculations choosing between
stock valuation and vendor price.

It does not decide what to charge. It establishes what something costs and how
well that is known; pricing decisions belong to the pricelist and to the person
quoting.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "category": "Inventory/Inventory",
    "depends": ["product", "stock"],
    "data": ["views/res_config_settings_views.xml"],
    "installable": True,
    "auto_install": False,
}
