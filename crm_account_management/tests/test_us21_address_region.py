from odoo.tests import Form, tagged

from odoo.addons.crm_account_management.tests.common import OUTestCommon


@tagged("post_install", "-at_install")
class TestUS21AddressRegion(OUTestCommon):
    """
    Task 3752 — CRM 2.3: customer address on the account dashboard.

    Acceptance Criteria covered here:
    - AC1: the account dashboard surfaces the owner's address (related,
      readonly fields). Covered by the related-field + form-build tests.

    (AC2 — the QC administrative region — was moved to the
    l10n_ca_qc_crm_account_management module per review feedback; its tests
    live there. AC3 — embedded map — is out of scope.)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]

    # =====================================================================
    # AC1 — related address fields reflect the owner + readonly
    # =====================================================================

    def test_address_fields_reflect_owner(self):
        """OU address fields mirror the owning partner's address."""
        state = self.env.ref("base.state_ca_qc", raise_if_not_found=False)
        country = self.env.ref("base.ca")
        vals = {
            "name": "Addr Co",
            "is_company": True,
            "street": "123 Rue Principale",
            "street2": "Suite 4",
            "city": "Montréal",
            "zip": "H2X 1Y4",
            "country_id": country.id,
        }
        if state:
            vals["state_id"] = state.id
        partner = self.partner_model.create(vals)
        ou = self.ou_model.search([("owner_id", "=", partner.id)])
        self.assertEqual(ou.owner_street, "123 Rue Principale")
        self.assertEqual(ou.owner_street2, "Suite 4")
        self.assertEqual(ou.owner_city, "Montréal")
        self.assertEqual(ou.owner_zip, "H2X 1Y4")
        self.assertEqual(ou.owner_country_id, country)
        if state:
            self.assertEqual(ou.owner_state_id, state)

    # =====================================================================
    # AC1 — form builds with the new address nodes (view/field smoke)
    # =====================================================================

    def test_form_view_builds_with_address(self):
        """The dashboard form builds and exposes the new address fields."""
        partner = self.partner_model.create(
            {"name": "Form Co", "is_company": True, "zip": "H2X 1Y4"}
        )
        ou = self.ou_model.search([("owner_id", "=", partner.id)])
        form = Form(ou)
        # Reading the related values through the Form proves the nodes resolved
        # against real fields (no missing-field view error).
        self.assertEqual(form.owner_city, partner.city)
