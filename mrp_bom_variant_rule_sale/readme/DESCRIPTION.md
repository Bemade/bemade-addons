Binds `mrp_bom_variant_rule` to sales. It installs itself automatically when
both dependencies are present, and it is a bridge rather than pure glue: it
adds behaviour of its own on the sales side, while leaving every judgement
about rules, generation and cost to the engine.

Configuring a variant on a quotation line is the moment a salesperson needs
its bill of materials to exist: it is what the line will be costed and priced
from. This module makes that the trigger. Setting a configured product on an
order line generates the variant's bill of materials if the ruleset can
produce one, records the bill of materials the line was actually costed from,
and surfaces its state — generated, superseded, or refused for an unmatched
slot — so the person quoting sees what stands behind the number before the
quotation goes out. A control on the line regenerates on demand after a
ruleset correction.

How far the component prices underneath that cost can be trusted is shown
alongside the state rather than folded into it. Whether the bill of materials
is the current one and whether its prices are fresh are independent
questions, and a single indicator could only ever answer one of them. The
assessment itself is the engine's; this module only relays it.

A refusal is recorded on the line rather than raised. A hole in the rule
table is a reason to tell the person quoting what is missing, not a reason to
stop them editing the quotation.

Generation is deliberately *not* hooked into price computation. Pricelist
evaluation runs in read paths — reports, portal pages, scheduled
recomputation — where creating records as a side effect would be surprising
and, in a report or a cron, wrong. Binding the trigger to the sales document
keeps generation tied to a person deliberately configuring something.
