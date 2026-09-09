from odoo import api, fields, models


class OrganizationalUnitMixin(models.AbstractModel):
    """Reverse-link mixin: gives any partner-bearing model a non-stored link
    back to the customer account(s) (``organizational.unit``) it belongs to,
    plus a smart button to navigate there.

    Resolution is delegated to ``res.partner._get_organizational_units()``,
    which is the exact inverse of ``organizational.unit._get_all_partners()``.

    Inherited (via ``_inherit``) by sale.order, crm.lead, account.move and
    stock.picking -- all of which expose a ``partner_id``.

    Non-stored (computed on read): a partner maps to 0, 1 or many OUs, and OU
    membership changes (member_ids edits, OU re-parenting, partner re-parenting)
    would otherwise require fragile cross-model store invalidation. Lists don't
    render smart buttons, so the per-form read cost is negligible.
    """

    _name = "organizational.unit.mixin"
    _description = "Organizational Unit Reverse-Link Mixin"

    organizational_unit_ids = fields.Many2many(
        "organizational.unit",
        string="Customer Accounts",
        compute="_compute_organizational_unit_ids",
        store=False,
        help="Customer accounts (organizational units) this record's partner "
             "belongs to.",
    )
    organizational_unit_count = fields.Integer(
        string="Customer Account Count",
        compute="_compute_organizational_unit_ids",
        store=False,
    )

    @api.depends("partner_id")
    def _compute_organizational_unit_ids(self):
        for record in self:
            ous = record.partner_id._get_organizational_units()
            record.organizational_unit_ids = ous
            record.organizational_unit_count = len(ous)

    def action_view_organizational_units(self):
        """Smart-button action: open the related customer account(s).

        0 -> close (button is hidden in that case anyway);
        1 -> open that OU's form;
        many -> a filtered list/form of those OUs.
        """
        self.ensure_one()
        ous = self.organizational_unit_ids
        if not ous:
            return {"type": "ir.actions.act_window_close"}
        if len(ous) == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "organizational.unit",
                "res_id": ous.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": "Customer Accounts",
            "res_model": "organizational.unit",
            "domain": [("id", "in", ous.ids)],
            "view_mode": "list,form",
            "target": "current",
        }
