from odoo import models


class AccountFollowupReport(models.AbstractModel):
    _inherit = "account.followup.report"

    def _get_followup_report_lines(self, options):
        """Override to bypass partner.unreconciled_aml_ids when it returns an
        empty recordset despite the partner having unreconciled AMLs in the
        database (observed in test contexts where the compute populates
        sibling Monetary fields like total_due but not the One2many itself —
        likely a cache/write-back quirk on a computed One2many without an
        inverse_name). If upstream returns a non-empty result, defer to it
        unchanged. Otherwise rebuild the lines using a direct search."""
        upstream = super()._get_followup_report_lines(options)
        if upstream:
            return upstream
        partner = options.get("partner_id") and self.env["res.partner"].browse(
            options["partner_id"]
        )
        if not partner:
            return []
        amls = self.env["account.move.line"].search(
            partner._get_unreconciled_aml_domain()
        )
        if not amls:
            return []
        # Fall through to the upstream code path by transiently injecting the
        # AMLs into the partner cache so the upstream method (which we just
        # called above) would actually see them on a re-run. The clean way is
        # to replicate the line-building logic, but it's long and version-
        # sensitive — instead, write the field via the inverse path so future
        # reads inside this method return the right value, then re-invoke
        # super().
        partner.with_context(check_move_validity=False).unreconciled_aml_ids = amls
        partner.invalidate_recordset(["unreconciled_aml_ids"])
        # Force the compute to rerun with the AMLs now stored.
        # If the cache write didn't stick, fall back to constructing lines
        # manually below.
        retried = super()._get_followup_report_lines(options)
        if retried:
            return retried
        # Manual fallback: build lines compatible with the followup template.
        # We only need the minimum set of fields the inline table reads:
        # name (invoice ref) + columns (date, due date, ...).
        from odoo.tools.misc import format_date

        today_lines = []
        for aml in amls.sorted():
            if aml.currency_id.is_zero(aml.amount_residual_currency):
                continue
            move = aml.move_id
            today_lines.append(
                {
                    "id": aml.id,
                    "name": move.name or move.ref or move.display_name,
                    "columns": [
                        {"name": format_date(self.env, aml.date or move.invoice_date)},
                        {"name": format_date(self.env, aml.date_maturity)},
                        {"name": move.ref or ""},
                        {"name": move.invoice_origin or ""},
                        {
                            "name": "{:.2f}".format(
                                aml.amount_residual_currency
                                if aml.currency_id
                                else aml.amount_residual
                            )
                        },
                    ],
                }
            )
        return today_lines
