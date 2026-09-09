from odoo.tests import Form, tagged
from odoo.fields import Command

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestUS10ReverseLinks(AccountTestInvoicingCommon):
    """
    US-10 (task 3753): reverse link from sale.order / crm.lead / account.move /
    stock.picking back to the customer account (organizational.unit).

    The resolution helper res.partner._get_organizational_units() must be the
    EXACT inverse of organizational.unit._get_all_partners():

        P in ou._get_all_partners()  <=>  ou in P._get_organizational_units()

    The correctness-critical tests assert against the FORWARD _get_all_partners()
    oracle, not the helper's own output, so they cannot pass under buggy inverse
    logic (e.g. a commercial_partner_id over-report).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.OU = cls.env["organizational.unit"]

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _ou_of(self, company):
        """The auto-created OU owned by a top-level company partner."""
        return self.OU.search([("owner_id", "=", company.id)])

    def _forward_truth(self, partner):
        """The forward oracle: every OU whose _get_all_partners() contains
        ``partner``. This is the ground truth the inverse must reproduce."""
        return self.OU.search([]).filtered(
            lambda ou: partner in ou._get_all_partners()
        )

    # ------------------------------------------------------------------ #
    # 1. 0 OUs
    # ------------------------------------------------------------------ #
    def test_01_zero_ous(self):
        contact = self.Partner.create({"name": "Lonely Contact", "is_company": False})
        self.assertFalse(
            contact._get_organizational_units(),
            "A standalone contact owning/membering nothing belongs to no OU.",
        )
        # a sale.order for it -> count 0
        so = self.env["sale.order"].create({"partner_id": contact.id})
        self.assertEqual(so.organizational_unit_count, 0)
        self.assertFalse(so.organizational_unit_ids)
        # and an account.move (invoice) for it -> count 0 (safe vendor-bill outcome)
        move = self.env["account.move"].create(
            {"move_type": "out_invoice", "partner_id": contact.id}
        )
        self.assertEqual(move.organizational_unit_count, 0)

    # ------------------------------------------------------------------ #
    # 2. 1 OU via owner
    # ------------------------------------------------------------------ #
    def test_02_one_ou_via_owner(self):
        company = self.Partner.create({"name": "Owner Co", "is_company": True})
        ou = self._ou_of(company)
        self.assertTrue(ou, "Top company auto-creates its OU.")

        so = self.env["sale.order"].create({"partner_id": company.id})
        self.assertEqual(so.organizational_unit_ids, ou)
        self.assertEqual(so.organizational_unit_count, 1)

    # ------------------------------------------------------------------ #
    # 3. 1 OU via owner's DIRECT contact (branch b)
    # ------------------------------------------------------------------ #
    def test_03_one_ou_via_direct_contact(self):
        company = self.Partner.create({"name": "Branch-B Co", "is_company": True})
        ou = self._ou_of(company)
        contact = self.Partner.create(
            {"name": "Direct Contact", "parent_id": company.id}
        )
        # forward oracle pins the (b) branch
        self.assertIn(
            contact, ou._get_all_partners(),
            "Forward: direct child of owner company is in the OU.",
        )
        self.assertEqual(
            contact._get_organizational_units(), self._forward_truth(contact),
            "Inverse must equal the forward oracle.",
        )
        self.assertEqual(contact._get_organizational_units(), ou)

    # ------------------------------------------------------------------ #
    # 4. 2-LEVEL HIERARCHY -- the defect-closing test
    # ------------------------------------------------------------------ #
    def test_04_two_level_hierarchy_no_over_report(self):
        # top company C (owns ou_c)
        c = self.Partner.create({"name": "Top C", "is_company": True})
        ou_c = self._ou_of(c)
        # intermediate NON-company contact D, direct child of C. Because D is not
        # a company, commercial_partner_id keeps climbing past it to C.
        d = self.Partner.create(
            {"name": "Dept D", "is_company": False, "parent_id": c.id}
        )
        # deep contact P, child of D -> commercial_partner_id == C but parent_id == D.
        # This is exactly the case the buggy commercial_partner_id inverse over-reported.
        p = self.Partner.create({"name": "Deep P", "parent_id": d.id})
        self.assertEqual(
            p.commercial_partner_id, c,
            "Sanity: P's commercial partner climbs past non-company D to C.",
        )
        self.assertEqual(p.parent_id, d, "Sanity: P's direct parent is D, not C.")

        forward = self._forward_truth(p)
        # the invariant, by construction
        self.assertEqual(p._get_organizational_units(), forward)
        # owner_id.child_ids is ONE level -> P is NOT a direct child of C ->
        # P not in ou_c._get_all_partners() -> ou_c must NOT be reported.
        self.assertNotIn(
            p, ou_c._get_all_partners(),
            "Forward: P is not a direct child of C, so not in C's OU.",
        )
        self.assertNotIn(
            ou_c, p._get_organizational_units(),
            "Inverse must NOT over-report ou_c (the commercial_partner_id bug).",
        )

    def test_04b_two_level_hierarchy_d_owns_ou(self):
        # Same shape, but D is top-level so it owns its own ou_d -> P IS its direct
        # child, so ou_d is correctly in the forward set and the inverse must match.
        d = self.Partner.create({"name": "Owner D", "is_company": True})
        ou_d = self._ou_of(d)
        p = self.Partner.create({"name": "Child of D", "parent_id": d.id})
        forward = self._forward_truth(p)
        self.assertIn(ou_d, forward)
        self.assertEqual(p._get_organizational_units(), forward)

    # ------------------------------------------------------------------ #
    # 5. 1 OU via explicit member (branch c)
    # ------------------------------------------------------------------ #
    def test_05_one_ou_via_member(self):
        company = self.Partner.create({"name": "Member Owner Co", "is_company": True})
        ou = self._ou_of(company)
        # a partner that is neither owner nor child of owner
        member = self.Partner.create({"name": "Explicit Member", "is_company": True})
        ou.write({"member_ids": [Command.link(member.id)]})

        self.assertIn(
            member, ou._get_all_partners(), "Forward: explicit member is in the OU."
        )
        self.assertIn(ou, member._get_organizational_units())
        self.assertEqual(member._get_organizational_units(), self._forward_truth(member))

    # ------------------------------------------------------------------ #
    # 6. Many OUs
    # ------------------------------------------------------------------ #
    def test_06_many_ous(self):
        # company owns ou_a; member of ou_b
        company = self.Partner.create({"name": "Multi Co", "is_company": True})
        ou_a = self._ou_of(company)
        other = self.Partner.create({"name": "Other Co", "is_company": True})
        ou_b = self._ou_of(other)
        ou_b.write({"member_ids": [Command.link(company.id)]})

        ous = company._get_organizational_units()
        self.assertEqual(ous, ou_a | ou_b)
        self.assertEqual(company._get_organizational_units(), self._forward_truth(company))

        so = self.env["sale.order"].create({"partner_id": company.id})
        self.assertEqual(so.organizational_unit_count, 2)
        action = so.action_view_organizational_units()
        self.assertEqual(action["res_model"], "organizational.unit")
        self.assertIn("list", action["view_mode"])
        self.assertEqual(set(action["domain"][0][2]), set((ou_a | ou_b).ids))

    # ------------------------------------------------------------------ #
    # 7. Ancestry (recursion is downward; inverse climbs up)
    # ------------------------------------------------------------------ #
    def test_07_ancestry(self):
        parent_company = self.Partner.create({"name": "Parent OU Co", "is_company": True})
        p_ou = self._ou_of(parent_company)
        child_company = self.Partner.create({"name": "Child OU Co", "is_company": True})
        c_ou = self._ou_of(child_company)
        c_ou.write({"parent_id": p_ou.id})

        # a member of the CHILD OU only
        member = self.Partner.create({"name": "Child Member", "is_company": True})
        c_ou.write({"member_ids": [Command.link(member.id)]})

        # forward: member is in c_ou AND (via downward recursion) in p_ou
        self.assertIn(member, c_ou._get_all_partners())
        self.assertIn(member, p_ou._get_all_partners())
        # inverse returns both ancestor and direct
        ous = member._get_organizational_units()
        self.assertIn(c_ou, ous)
        self.assertIn(p_ou, ous)
        self.assertEqual(ous, self._forward_truth(member))

        # negative direction: a member of the PARENT only must NOT pull in the child
        parent_only = self.Partner.create({"name": "Parent Member", "is_company": True})
        p_ou.write({"member_ids": [Command.link(parent_only.id)]})
        self.assertNotIn(
            parent_only, c_ou._get_all_partners(),
            "Forward recursion is downward only -- parent member not in child OU.",
        )
        self.assertNotIn(c_ou, parent_only._get_organizational_units())
        self.assertIn(p_ou, parent_only._get_organizational_units())

    # ------------------------------------------------------------------ #
    # 8. Form smoke + single-OU action
    # ------------------------------------------------------------------ #
    def test_08_form_smoke_and_single_action(self):
        company = self.Partner.create({"name": "Form Co", "is_company": True})
        ou = self._ou_of(company)
        with Form(self.env["sale.order"]) as form:
            form.partner_id = company
            # count field is present and computed without error
            self.assertEqual(form.organizational_unit_count, 1)
        so = form.save()
        action = so.action_view_organizational_units()
        self.assertEqual(action["res_model"], "organizational.unit")
        self.assertEqual(action["res_id"], ou.id)
        self.assertEqual(action["view_mode"], "form")
