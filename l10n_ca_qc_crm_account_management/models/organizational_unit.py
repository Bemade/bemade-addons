from odoo import api, fields, models

from .qc_regions import QC_REGIONS, fsa_to_region


class OrganizationalUnit(models.Model):
    _inherit = "organizational.unit"

    # --- QC administrative region (AC2): stored computed, group/filter-able ---
    qc_administrative_region = fields.Selection(
        selection=QC_REGIONS,
        string="QC Administrative Region",
        compute="_compute_qc_administrative_region",
        store=True,
        help="One of the 17 official Quebec administrative regions, derived "
        "from the owning partner's postal-code FSA. Approximate for "
        "unmapped FSAs (curated subset).",
    )

    @api.depends("owner_id.zip")
    def _compute_qc_administrative_region(self):
        """Derive the QC administrative region from the owner's postal FSA.

        Stored so it can be grouped/filtered server-side. Recomputes whenever
        the owning partner's zip changes. Derivation logic lives in the pure
        ``fsa_to_region`` helper (see ``models/qc_regions.py``).
        """
        for record in self:
            record.qc_administrative_region = fsa_to_region(
                record.owner_id.zip if record.owner_id else False
            )
