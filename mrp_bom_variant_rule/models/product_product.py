# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

import hashlib

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_round

from ..tools.expression import ExpressionError, check_expression

BOM_CHANGE_POLICY_PARAM = "mrp_bom_variant_rule.bom_change_policy"
DEFAULT_BOM_CHANGE_POLICY = "overwrite"


class ProductProduct(models.Model):
    _inherit = "product.product"

    bom_rule_set_id = fields.Many2one(
        comodel_name="mrp.bom.rule.set",
        string="BOM Ruleset",
        compute="_compute_bom_rule_set_id",
        help="The ruleset bound to this variant's template, if any. Only a "
        "variant that has one can have a bill of materials generated for it.",
    )

    @api.depends("product_tmpl_id")
    def _compute_bom_rule_set_id(self):
        """Deliberately not stored: the binding lives on the ruleset, so a
        stored mirror here would go wrong the moment a ruleset is pointed at a
        different template."""
        rule_sets = self.env["mrp.bom.rule.set"]
        for product in self:
            product.bom_rule_set_id = rule_sets._for_product(product)

    def _bom_rule_resolve_lines(self, rule_set):
        """Resolve the ruleset against this variant.

        Returns a list of ``(rule, component, quantity, uom)`` for the slots
        that matched. The component is passed alongside the rule because a
        mapped rule has no single component of its own -- it has a table, and
        which row applies depends on the variant being resolved. Raises ``UserError`` naming every problem found rather than
        the first, so one round trip tells a rule author everything that is
        wrong.
        """
        self.ensure_one()
        params = self._bom_rule_param_context()
        values = self.product_template_attribute_value_ids.mapped(
            "product_attribute_value_id"
        )
        resolved = []
        unmatched = []
        failures = []
        for slot in rule_set.slot_ids.sorted(lambda s: (s.sequence, s.id)):
            rule, product, gaps = None, self.env["product.product"], []
            answered_nothing = False
            for candidate in slot.rule_ids.sorted(lambda r: (r.sequence, r.id)):
                if not candidate._matches(self):
                    continue
                if candidate._bom_rule_supplies_nothing(values):
                    # An answer, not an absence: this variant does not include
                    # a component here. The slot is satisfied and emits no line.
                    answered_nothing = True
                    break
                component, uom_override = candidate._bom_rule_component(values)
                if not component:
                    # A mapped rule whose table has no row for this variant is
                    # no more use than one whose conditions did not hold. Keep
                    # looking rather than settling for a plausible substitute,
                    # but remember which cell was blank: "no rule matches" sends
                    # someone hunting, whereas naming the empty cell is a
                    # question they can answer in one edit.
                    gaps.append(candidate._bom_rule_gap(values))
                    continue
                rule, product = candidate, component
                break
            if answered_nothing:
                continue
            if not rule:
                if slot.required:
                    unmatched.append((slot.name, [g for g in gaps if g]))
                continue
            uom = uom_override or rule.product_uom_id or product.uom_id
            try:
                qty = rule._compute_qty(params)
            except ExpressionError as err:
                failures.append(
                    _(
                        "%(slot)s: quantity %(expr)r could not be computed - "
                        "%(reason)s",
                        slot=slot.name,
                        expr=rule.qty_expr,
                        reason=str(err),
                    )
                )
                continue
            qty = float_round(qty, precision_rounding=uom.rounding)
            # A rule may legitimately decline to contribute by resolving to
            # zero; that is not an error, it simply emits no line.
            if qty:
                resolved.append((rule, product, qty, uom))

        if unmatched or failures:
            configuration = ", ".join(
                self.product_template_attribute_value_ids.mapped("name")
            ) or _("no attribute values")
            problems = [
                _(
                    "%(slot)s: nothing chosen for %(gaps)s",
                    slot=name,
                    gaps=", ".join(gaps),
                )
                if gaps
                else _("%(slot)s: no rule matches", slot=name)
                for name, gaps in unmatched
            ] + failures
            raise UserError(
                _(
                    "No bill of materials can be generated for %(product)s "
                    "(%(configuration)s):\n%(problems)s",
                    product=self.name,
                    configuration=configuration,
                    problems="\n".join("  - %s" % p for p in problems),
                )
            )
        return resolved

    def _bom_rule_bom(self):
        """This variant's existing generated bill of materials, if any.

        Archived bills of materials are excluded by the default active test:
        a superseded revision belongs to the order that consumed it, never to
        the variant as it stands now.
        """
        self.ensure_one()
        return self.env["mrp.bom"].search(
            [
                ("product_id", "=", self.id),
                ("generated_rule_set_id", "!=", False),
            ],
            limit=1,
        )

    def _bom_rule_consumed_params(self, resolved):
        """The parameter names the resolved rules actually referenced.

        Only these belong in the fingerprint. A parameter no rule reads cannot
        have influenced the result, and folding it in would report bills of
        materials stale for edits that could not have changed them.
        """
        self.ensure_one()
        consumed = set()
        for rule, _component, _qty, _uom in resolved:
            consumed |= check_expression(rule.qty_expr)
        return consumed

    def _bom_rule_fingerprint_payload(self, rule_set, resolved):
        """Canonical text of the inputs that produced a bill of materials.

        Everything is named rather than referenced by id, and every collection
        is sorted, so the payload depends on what the inputs mean and not on
        the ids or the ordering the database happened to hand us. Nothing
        time-varying appears: two runs a year apart over unchanged data have
        to agree.
        """
        self.ensure_one()
        params = self._bom_rule_param_context()
        consumed = self._bom_rule_consumed_params(resolved)
        attributes = sorted(
            "%s=%s" % (ptav.attribute_id.name, ptav.name)
            for ptav in self.product_template_attribute_value_ids
        )
        values = sorted(
            "%s=%.6f" % (name, params[name])
            for name in consumed
            if name in params
        )
        return "\n".join(
            [
                "revision=%d" % rule_set.revision,
                "attributes=" + "|".join(attributes),
                "parameters=" + "|".join(values),
            ]
        )

    def _bom_rule_fingerprint(self, rule_set, resolved):
        """Digest of ``_bom_rule_fingerprint_payload``."""
        self.ensure_one()
        payload = self._bom_rule_fingerprint_payload(rule_set, resolved)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _bom_rule_bom_values(self, rule_set, resolved):
        """Values for a generated bill of materials of this variant."""
        self.ensure_one()
        return {
            "product_tmpl_id": self.product_tmpl_id.id,
            # Scoped to the variant, never left template-wide: a generated
            # bill of materials describes one configuration only.
            "product_id": self.id,
            "product_qty": 1.0,
            "product_uom_id": self.uom_id.id,
            "type": "normal",
            "generated_rule_set_id": rule_set.id,
            "generated_fingerprint": self._bom_rule_fingerprint(
                rule_set, resolved
            ),
            "bom_line_ids": [Command.clear()]
            + [
                Command.create(
                    {
                        "product_id": product.id,
                        "product_qty": qty,
                        "product_uom_id": uom.id,
                    }
                )
                for rule, product, qty, uom in resolved
            ],
        }

    def _bom_rule_hand_built_boms(self):
        """Bills of materials for this variant that a human wrote.

        A template-wide bill of materials answers for this variant too, so it
        counts: generating alongside it would leave two candidates.
        """
        self.ensure_one()
        return self.env["mrp.bom"].search(
            [
                ("product_tmpl_id", "=", self.product_tmpl_id.id),
                ("product_id", "in", [False, self.id]),
                ("generated_rule_set_id", "=", False),
            ]
        )

    def _bom_rule_generate(self, force=False):
        """Return this variant's generated bill of materials, building it if
        it does not exist yet.

        Generation is lazy and idempotent: without ``force`` an existing
        generated bill of materials is returned untouched. Raises
        ``UserError`` when the rules cannot produce a complete bill of
        materials for this configuration, or when a hand-built one is in the
        way.
        """
        self.ensure_one()
        rule_set = self.env["mrp.bom.rule.set"]._for_product(self)
        if not rule_set:
            return self.env["mrp.bom"]

        hand_built = self._bom_rule_hand_built_boms()
        if hand_built:
            # A person's bill of materials outranks a rule, whatever the
            # caller asked for. Adopting or replacing it would discard work
            # the rules cannot reconstruct.
            raise UserError(
                _(
                    "%(product)s already has a bill of materials that was not "
                    "produced by a ruleset (%(bom)s). It will not be "
                    "overwritten. Archive or delete it first if the rules "
                    "should take over.",
                    product=self.display_name,
                    bom=", ".join(hand_built.mapped("display_name")),
                )
            )

        existing = self._bom_rule_bom()
        if existing and not force:
            return existing

        resolved = self._bom_rule_resolve_lines(rule_set)
        if not existing:
            bom = self.env["mrp.bom"].create(
                self._bom_rule_bom_values(rule_set, resolved)
            )
        elif self._bom_rule_change_policy() == "revision":
            # There is something to replace and the business has asked for
            # replacements to be traceable, so hand the decision to the
            # supersede hook rather than writing over the record.
            bom = self._bom_rule_supersede(existing, resolved)
        else:
            existing.write(self._bom_rule_bom_values(rule_set, resolved))
            bom = existing
        # Recorded after the lines exist, and on every path that produced new
        # ones, so the confidence always describes the components actually
        # standing on the bill of materials.
        bom._bom_rule_compute_cost_confidence()
        return bom

    @api.model
    def _bom_rule_change_policy(self):
        """Whether an existing generated bill of materials may be rewritten.

        This is a product lifecycle decision and nothing else. Odoo freezes a
        manufacturing order's raw moves at confirmation, so rewriting the
        bill of materials it was built from cannot change what that order
        produces; the state of any manufacturing order therefore has no
        bearing on the answer. What the setting expresses is whether the
        business treats a generated bill of materials as a disposable working
        document or as a controlled revision.
        """
        policy = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(BOM_CHANGE_POLICY_PARAM)
        )
        if policy not in ("overwrite", "revision"):
            return DEFAULT_BOM_CHANGE_POLICY
        return policy

    def _bom_rule_supersede(self, existing_bom, resolved):
        """Produce the bill of materials that replaces ``existing_bom``.

        The extension point for revision control. This implementation is the
        one available without a change-management system: copy the resolved
        lines onto a fresh bill of materials, point it back at the one it
        replaces and archive that. Installing a bridge to an engineering
        change process overrides this to route the same replacement through
        that process instead.

        Called only under the ``revision`` policy, and never for a variant's
        first bill of materials: there is nothing to supersede in either case.
        """
        self.ensure_one()
        values = self._bom_rule_bom_values(
            existing_bom.generated_rule_set_id, resolved
        )
        values["generated_predecessor_id"] = existing_bom.id
        bom = self.env["mrp.bom"].create(values)
        # Archived rather than deleted: a manufacturing order or a quotation
        # may still point here, and that record of what was quoted or built
        # has to stay readable.
        existing_bom.active = False
        return bom

    def action_bom_rule_regenerate(self):
        """Regenerate control of the product form."""
        self.ensure_one()
        bom = self._bom_rule_generate(force=True)
        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.bom",
            "res_id": bom.id,
            "view_mode": "form",
            "target": "current",
        }

    def _bom_rule_param_context(self):
        """Merge the named parameters of every attribute value this variant
        carries into a single evaluation context.

        A parameter declared with conflicting values by two of the variant's
        own attribute values is ambiguous: there is no defensible way to pick
        one, and picking silently would produce a quantity nobody can explain.
        """
        self.ensure_one()
        context = {}
        origin = {}
        for ptav in self.product_template_attribute_value_ids:
            value = ptav.product_attribute_value_id
            for param in value.param_ids:
                if param.name in context and context[param.name] != param.value:
                    raise UserError(
                        _(
                            "Parameter %(name)r is defined as %(first)s by "
                            "%(first_value)s and as %(second)s by "
                            "%(second_value)s on the same variant. Resolve "
                            "the conflict before generating a bill of "
                            "materials.",
                            name=param.name,
                            first=context[param.name],
                            first_value=origin[param.name],
                            second=param.value,
                            second_value=value.display_name,
                        )
                    )
                context[param.name] = param.value
                origin[param.name] = value.display_name
        return context
