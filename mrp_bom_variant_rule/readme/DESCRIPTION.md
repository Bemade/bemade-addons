Configure-to-order products have a combinatorial explosion problem: a product
template with six attributes can address tens of thousands of valid
configurations, but only a handful ever get a hand-built bill of materials.
The rest are quoted from a placeholder price and assembled from tribal
knowledge, or worked around by cloning a one-off product per sales order.

This module lets you describe, once, **how** a bill of materials is assembled
for such a template, and then generates a concrete ``mrp.bom`` for whichever
combination a customer actually asks for.

Component slots
---------------

A ruleset decomposes the product into named **slots** — the vessel, the
control valve, the media, the piping — each of which may be flagged
*required*. Rules are matched per slot, in sequence, first match wins.

Named attribute parameters
--------------------------

Attribute values carry named numeric **parameters** rather than the engine
knowing anything about the product domain. A value may declare
``volume_ft3 = 1.5`` and ``height_in = 54``; another may declare
``trains = 2``. A rule's quantity is then a restricted arithmetic expression
over those parameters, evaluated against the variant being generated, so a
single rule expresses quantities that vary continuously across the
configuration space instead of requiring one bill-of-materials line per
combination.

Generation is lazy
------------------

Nothing is generated up front. A variant's bill of materials is materialised
the first time it is needed — when the variant is first priced — and can be
regenerated on demand from the product form. A scheduled action *reports*
bills of materials that have fallen out of step with their ruleset; it never
rewrites them silently.

Refusal over silent incompleteness
----------------------------------

If any required slot has no matching rule for a combination, generation is
refused with a message naming the unmatched slot and the attribute values
that reached it. A partially populated bill of materials that under-costs a
quotation is a worse outcome than no bill of materials at all.

Generated bills of materials are stamped with the ruleset and a fingerprint of
the inputs that produced them.

Change policy
-------------

What regeneration is allowed to do to a generated bill of materials that
already exists is a single setting under *Manufacturing*. Under **overwrite**,
the default, regeneration rewrites the existing bill of materials in place:
one record per configuration, nothing accumulates, and no record survives of
what a past quotation was costed from. Under **revision**, an existing bill of
materials is never rewritten — regeneration produces a new one, records the
one it replaced, and archives that.

This is a product lifecycle decision and nothing else. Odoo freezes a
manufacturing order's components when the order is confirmed, so neither
choice can alter an order already under way.

Cost confidence
---------------

Generation records which components carry no vendor price, or a price older
than a configurable age, and exposes the result on the generated bill of
materials. A cost rollup built on stale inputs stays visible as such rather
than presenting itself as a firm number, and the same data doubles as a
worklist of the components most worth repricing.

This module does not price anything itself. Pair it with
``product_pricelist_bom_cost`` to drive a sale price from the generated bill
of materials' cost rollup.
