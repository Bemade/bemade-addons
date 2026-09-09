from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    preamble = fields.Html(
        string="Quotation Preamble",
        help="HTML content to display at the beginning of the quotation PDF",
        sanitize=True,
        sanitize_tags=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Set default preamble from company settings when creating a new sale order."""
        records = super().create(vals_list)
        for rec in records:
            if not rec.preamble and rec.company_id.default_quotation_preamble:
                rec.preamble = rec.company_id.default_quotation_preamble
        return records
