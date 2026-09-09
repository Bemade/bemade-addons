from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ytd_metric_basis = fields.Selection(
        selection=[
            ("fiscal", "Fiscal-YTD sales"),
            ("bookings", "Calendar-YTD bookings"),
        ],
        string="Dashboard YTD Metric",
        default="fiscal",
        config_parameter="crm_account_management.ytd_metric_basis",
        help="Basis for the customer-account dashboard's headline YTD sales "
        "figure. 'Fiscal-YTD sales' (default) sums posted customer invoices "
        "over the fiscal year to date. 'Calendar-YTD bookings' sums confirmed "
        "sale orders (bookings) over the current calendar year to date, "
        "compared against the same calendar window last year.",
    )

    def set_values(self):
        """Persist the config parameter, then recompute the stored dashboard
        YTD fields on all organizational units.

        ``ytd_metric_basis`` is stored as an ``ir.config_parameter`` (via the
        ``config_parameter`` shorthand), which is outside the ORM dependency
        graph, so changing it does not auto-invalidate the stored ``ytd_sales``
        fields. Recompute them here so the dashboard reflects the new basis
        immediately rather than only after the nightly ``_cron_refresh_metrics``.
        """
        super().set_values()
        self.env["organizational.unit"].search([])._compute_sales_metrics()
