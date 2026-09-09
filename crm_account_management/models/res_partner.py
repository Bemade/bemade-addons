from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    owned_organizational_unit_ids = fields.One2many(
        "organizational.unit",
        "owner_id",
        string="Owned Customer Accounts",
        help="Organizational units (customer accounts) owned by this partner.",
    )
    organizational_unit_ids = fields.Many2many(
        "organizational.unit",
        string="Member Of Accounts",
        help="Organizational units this partner is an explicit member of.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner in partners:
            if partner.is_company and not partner.parent_id:
                self.env["organizational.unit"].sudo().create({
                    "name": partner.name,
                    "owner_id": partner.id,
                })
        return partners

    def write(self, vals):
        # Capture old names before write so we can detect which OUs were in sync
        old_names = {}
        if "name" in vals:
            for partner in self:
                old_names[partner.id] = partner.name
        res = super().write(vals)
        if "name" in vals:
            for partner in self:
                for ou in partner.owned_organizational_unit_ids:
                    if ou.name == old_names.get(partner.id):
                        ou.sudo().write({"name": partner.name})
        return res

    def _get_organizational_units(self):
        """Return every organizational.unit this partner belongs to.

        This is the EXACT inverse of
        ``organizational.unit._get_all_partners()`` (organizational_unit.py).

        Invariant (the correctness contract):
            P in ou._get_all_partners()  <=>  ou in P._get_organizational_units()

        Forward membership predicate -- ``P in ou._get_all_partners()`` holds iff
        at least one of:
            (a) ou.owner_id == P
            (b) ou.owner_id == P.parent_id   (P is a DIRECT child contact of the
                owner company; mirrors the one-level ``owner_id.child_ids``, NOT
                commercial_partner_id which would climb to the topmost ancestor)
            (c) P in ou.member_ids
            (d) the same predicate holds for some DESCENDANT OU of ou
                (the forward recursion into child_ids).

        Inverting it:
            1. direct = OUs satisfying (a) OR (b) OR (c).
            2. result = direct PLUS all ancestors of direct (climb parent_id up the
               organizational.unit tree -- the inverse of the downward recursion).
        """
        OU = self.env["organizational.unit"]
        if not self:
            return OU
        result = OU
        for partner in self:
            # 1. Direct matches: branches (a), (b), (c).
            #    (a) owner_id == partner       -- also == partner.owned_organizational_unit_ids
            #    (b) owner_id == partner.parent_id  (one level, mirroring owner_id.child_ids)
            #    (c) partner in member_ids
            owner_candidates = partner | partner.parent_id
            direct = OU.search([
                "|", "|",
                ("owner_id", "in", owner_candidates.ids),
                ("member_ids", "in", partner.ids),
                ("id", "in", partner.owned_organizational_unit_ids.ids),
            ])
            # 2. Ancestors: climb parent_id until no new OUs appear
            #    (bounded -- _check_parent_recursion forbids cycles).
            partner_result = direct
            frontier = direct.parent_id
            while frontier - partner_result:
                partner_result |= frontier
                frontier = frontier.parent_id
            result |= partner_result
        return result

    def action_view_organizational_unit(self):
        """Navigate to the partner's organizational unit."""
        self.ensure_one()
        ou = self.owned_organizational_unit_ids[:1] or self.organizational_unit_ids[:1]
        if not ou:
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "res_model": "organizational.unit",
            "res_id": ou.id,
            "view_mode": "form",
            "target": "current",
        }
