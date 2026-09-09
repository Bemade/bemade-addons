from odoo.tests import Form, tagged

from odoo.addons.crm_account_management.tests.common import OUTestCommon
from odoo.addons.l10n_ca_qc_crm_account_management.models.qc_regions import (
    QC_REGIONS,
    fsa_to_region,
)


@tagged("post_install", "-at_install")
class TestQCAdministrativeRegion(OUTestCommon):
    """
    Task 3752 — AC2: QC administrative region derived from the postal-code FSA.

    Quebec-specific overlay moved out of the shared crm_account_management
    module into l10n_ca_qc_crm_account_management per review feedback.

    Covers:
    - the pure fsa_to_region helper (no ORM; the core derivation logic),
    - the stored compute on organizational.unit + recompute on zip change,
    - the read_group (group/filter) behaviour,
    - the form smoke build with the QC region node.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]

    # =====================================================================
    # fsa_to_region pure helper (no ORM; the core derivation logic)
    # =====================================================================

    def test_fsa_mapped_montreal(self):
        """An H-prefix Montréal FSA resolves to Montréal (06)."""
        self.assertEqual(fsa_to_region("H2X 1Y4"), "06")

    def test_fsa_mapped_quebec_city(self):
        """A G1x Québec-City FSA resolves to Capitale-Nationale (03)."""
        self.assertEqual(fsa_to_region("G1R 2B5"), "03")

    def test_fsa_mapped_monteregie(self):
        """A J4x Montérégie FSA resolves to Montérégie (16)."""
        self.assertEqual(fsa_to_region("J4K 1A1"), "16")

    def test_fsa_mapped_laval(self):
        """An H7x FSA resolves to Laval (13), distinct from Montréal."""
        self.assertEqual(fsa_to_region("H7N 5K1"), "13")

    def test_fsa_mapped_lanaudiere(self):
        """J7K (Repentigny) is curated to Lanaudière (14)."""
        self.assertEqual(fsa_to_region("J7K 3C5"), "14")

    def test_fsa_mapped_outaouais(self):
        """A J8X Gatineau FSA resolves to Outaouais (07)."""
        self.assertEqual(fsa_to_region("J8X 2V1"), "07")

    def test_fsa_normalises_case_and_spaces(self):
        """Lower-case / extra-spaced input normalises to the same region."""
        self.assertEqual(fsa_to_region("  h2x1y4 "), "06")
        self.assertEqual(fsa_to_region("g1r2b5"), "03")

    def test_fsa_first_letter_fallback(self):
        """Unmapped QC FSAs fall back coarsely by first letter."""
        # H-prefix not in the curated dict → Montréal-area (06)
        self.assertEqual(fsa_to_region("H0H 0H0"), "06")
        # G-prefix not in the curated dict → eastern QC / Capitale-Nationale (03)
        self.assertEqual(fsa_to_region("G0A 0A0"), "03")
        # J-prefix not in the curated dict → western QC / Montérégie (16)
        self.assertEqual(fsa_to_region("J0J 0J0"), "16")

    def test_fsa_non_quebec_returns_false(self):
        """Non-QC postal codes (Toronto/Ottawa-ON) get no QC region."""
        self.assertFalse(fsa_to_region("M5V 2T6"))  # Toronto
        self.assertFalse(fsa_to_region("K1A 0B1"))  # Ottawa (ON)

    def test_fsa_empty_or_short_returns_false(self):
        """Empty / None / too-short input returns False."""
        self.assertFalse(fsa_to_region(""))
        self.assertFalse(fsa_to_region(None))
        self.assertFalse(fsa_to_region("H2"))

    def test_qc_regions_complete(self):
        """The selection lists all 17 official regions, codes 01–17."""
        codes = [code for code, _label in QC_REGIONS]
        self.assertEqual(codes, [f"{i:02d}" for i in range(1, 18)])

    # =====================================================================
    # stored compute on organizational.unit + recompute on zip change
    # =====================================================================

    def test_region_computed_on_create(self):
        """A company with a QC zip yields an OU with the derived region."""
        partner = self.partner_model.create(
            {"name": "Mtl Co", "is_company": True, "zip": "H2X 1Y4"}
        )
        ou = self.ou_model.search([("owner_id", "=", partner.id)])
        self.assertEqual(ou.qc_administrative_region, "06")

    def test_region_recomputes_on_zip_change(self):
        """Changing the owner's zip recomputes the stored region (depends)."""
        partner = self.partner_model.create(
            {"name": "Movers Inc", "is_company": True, "zip": "G1R 2B5"}
        )
        ou = self.ou_model.search([("owner_id", "=", partner.id)])
        self.assertEqual(ou.qc_administrative_region, "03")

        partner.write({"zip": "J4K 1A1"})
        self.assertEqual(
            ou.qc_administrative_region,
            "16",
            "Region must recompute when owner zip changes",
        )

    def test_region_false_for_non_qc(self):
        """A non-QC owner zip leaves the region empty."""
        partner = self.partner_model.create(
            {"name": "TO Co", "is_company": True, "zip": "M5V 2T6"}
        )
        ou = self.ou_model.search([("owner_id", "=", partner.id)])
        self.assertFalse(ou.qc_administrative_region)

    def test_region_is_groupable(self):
        """The stored region buckets records via read_group (group/filter)."""
        p1 = self.partner_model.create(
            {"name": "A Co", "is_company": True, "zip": "H2X 1Y4"}
        )
        p2 = self.partner_model.create(
            {"name": "B Co", "is_company": True, "zip": "G1R 2B5"}
        )
        groups = self.ou_model.read_group(
            [("owner_id", "in", [p1.id, p2.id])],
            fields=["qc_administrative_region"],
            groupby=["qc_administrative_region"],
        )
        buckets = {g["qc_administrative_region"] for g in groups}
        self.assertIn("06", buckets)
        self.assertIn("03", buckets)

    # =====================================================================
    # form builds with the QC region node (view/field smoke)
    # =====================================================================

    def test_form_view_builds_with_qc_region(self):
        """The dashboard form builds and exposes the QC region field."""
        partner = self.partner_model.create(
            {"name": "Form Co", "is_company": True, "zip": "H2X 1Y4"}
        )
        ou = self.ou_model.search([("owner_id", "=", partner.id)])
        form = Form(ou)
        # Reading the computed value through the Form proves the node resolved
        # against a real field (no missing-field view error).
        self.assertEqual(form.qc_administrative_region, "06")
