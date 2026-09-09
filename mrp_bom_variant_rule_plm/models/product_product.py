# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

ECO_TYPE_PARAM = "mrp_bom_variant_rule_plm.eco_type_id"
AUTO_APPLY_PARAM = "mrp_bom_variant_rule_plm.eco_auto_apply"
DEFAULT_ECO_TYPE_XMLID = "mrp_plm.ecotype_bom_update"

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _bom_rule_eco_type(self):
        """The ECO type new revisions are filed under.

        Held in ``ir.config_parameter`` rather than on ``res.company``
        because ``mrp.eco.type`` itself is not company-scoped: a per-company
        setting would promise a distinction the underlying model cannot make.

        Defaults to mrp_plm's own "BOM Updates". This module ships no ECO
        type of its own; an installation's ECO list is a thing people read,
        and adding a category to it that only a rule engine ever files into
        fragments that list for no benefit.
        """
        param = (
            self.env["ir.config_parameter"].sudo().get_param(ECO_TYPE_PARAM)
        )
        if param:
            try:
                eco_type = self.env["mrp.eco.type"].browse(int(param)).exists()
            except (TypeError, ValueError):
                eco_type = self.env["mrp.eco.type"]
            if eco_type:
                return eco_type
        return self.env.ref(
            DEFAULT_ECO_TYPE_XMLID, raise_if_not_found=False
        ) or self.env["mrp.eco.type"]

    @api.model
    def _bom_rule_eco_auto_apply(self):
        """Whether a rule-driven ECO is applied without waiting for a person.

        Stored as ``"1"``/``"0"`` rather than as a bare boolean because
        ``ir.config_parameter.set_param`` deletes a parameter whose value is
        falsy. A boolean parameter that defaults to True could therefore
        never be turned off: the deletion would send the next read straight
        back to the default.
        """
        param = (
            self.env["ir.config_parameter"].sudo().get_param(AUTO_APPLY_PARAM)
        )
        if param is False or param is None:
            return True
        return param not in ("0", "False", "")

    def _bom_rule_supersede(self, existing_bom, resolved):
        """File the replacement as an engineering change order.

        With a change-management system installed, a generated bill of
        materials is revised the way every other bill of materials is
        revised. The bridge contributes one thing the rule engine knows and
        mrp_plm does not — the component lines — and delegates the rest:
        mrp_plm copies the bill of materials, bumps its version, links it to
        its predecessor, computes the difference and, on approval, activates
        it.
        """
        self.ensure_one()
        eco_type = self._bom_rule_eco_type()
        if not eco_type:
            # Nothing to file against. Falling back to the plain copy is
            # better than refusing to regenerate at all.
            _logger.warning(
                "No ECO type is configured and %s is missing; revising %s "
                "as a plain bill-of-materials copy.",
                DEFAULT_ECO_TYPE_XMLID,
                self.display_name,
            )
            return super()._bom_rule_supersede(existing_bom, resolved)

        rule_set = existing_bom.generated_rule_set_id
        # Generation is a consequence of configuring a product, not of a
        # person operating the change-management application. Requiring the
        # engineering-change rights here would put configuration out of reach
        # of the people the module exists to serve.
        eco = (
            self.env["mrp.eco"]
            .sudo()
            .with_context(default_type_id=eco_type.id)
            .create(
                {
                    "name": _(
                        "%(product)s - %(rule_set)s",
                        product=self.display_name,
                        rule_set=rule_set.display_name,
                    ),
                    "type": "bom",
                    "type_id": eco_type.id,
                    "product_tmpl_id": self.product_tmpl_id.id,
                    "bom_id": existing_bom.id,
                }
            )
        )
        eco.action_new_revision()

        new_bom = eco.new_bom_id
        values = self._bom_rule_bom_values(rule_set, resolved)
        # The generation stamps are copy=False, so the revision mrp_plm just
        # took carries none of them. Without them the new bill of materials
        # would not be recognised as this variant's generated one once it
        # goes active.
        values["generated_predecessor_id"] = existing_bom.id
        new_bom.write(values)

        if self._bom_rule_eco_auto_apply() and self._bom_rule_eco_apply(eco):
            return new_bom
        # The change is filed but not approved. Until somebody approves it,
        # the variant's bill of materials is still the old one, and anything
        # costed in the meantime has to be costed from that.
        return existing_bom

    def _bom_rule_eco_apply(self, eco):
        """Advance ``eco`` to a stage that allows applying, then apply it.

        Returns whether the change was actually applied. A new ECO starts in
        the type's first stage, which does not allow applying, so the stage
        has to be moved first; mrp_plm refuses that move while approvals are
        outstanding. That refusal is the system working as configured, so it
        leaves the ECO pending rather than propagating as a failure to
        regenerate.
        """
        self.ensure_one()
        stage = self.env["mrp.eco.stage"].search(
            [
                ("type_ids", "in", eco.type_id.id),
                ("allow_apply_change", "=", True),
            ],
            limit=1,
        )
        if not stage:
            return False
        try:
            eco.stage_id = stage
        except UserError:
            _logger.info(
                "ECO %s cannot be applied automatically because approvals "
                "are outstanding; leaving it for a reviewer.",
                eco.name,
            )
            return False
        if not eco.allow_apply_change:
            return False
        eco.action_apply()
        return eco.state == "done"
