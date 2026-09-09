Glue between ``mrp_bom_variant_rule`` and Odoo's Product Lifecycle Management
application. It installs itself as soon as both are present and adds no
capability of its own; it changes *how* one existing capability is carried
out.

`mrp_bom_variant_rule` offers two policies for what regeneration may do to a
generated bill of materials that already exists. Under **overwrite** it is
rewritten in place, and this module has nothing to say. Under **revision** it
is never rewritten: a replacement is produced and the original retired. Left
to itself, the core module does that with a bare copy, which is the best it
can do without a change-management system.

With PLM installed there is a better answer, and it is the one the rest of the
system already uses: an **engineering change order**. This module routes the
revision through one. It creates an ``mrp.eco`` against the existing bill of
materials, lets mrp_plm take the new revision — the version bump, the link to
the predecessor, the difference report — and contributes the one thing the
rule engine knows and mrp_plm does not, namely the component lines the rules
now resolve to. Nothing is re-implemented: the old-versus-new diff on the
change order is mrp_plm's own.

Two settings, under *Manufacturing*, and both only matter under the revision
policy:

**Change order type.** Which ECO type rule-driven revisions are filed under.
It defaults to the standard *BOM Updates* type. This module deliberately ships
no ECO type of its own: an installation's list of change order types is
something people read and organise their work around, and adding a category to
it that only a rule engine ever files into would fragment it for no benefit.

**Apply revisions immediately.** On by default, which makes the regenerated
bill of materials active at once — the change order becomes a record of what
happened rather than a gate. Turn it off and every rule-driven revision waits
for a person: the change order is filed for approval and, until somebody
approves it, the **previous** bill of materials is still the active one and is
still what quotations are costed from. That is the point of the option. A
price given to a customer should not move because an engineer edited a rule
table that afternoon.
