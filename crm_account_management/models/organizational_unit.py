from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
from datetime import date
from dateutil.relativedelta import relativedelta


class OrganizationalUnit(models.Model):
    _name = "organizational.unit"
    _description = "Organizational Unit (Customer Account)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    @api.model
    def _create_ous_for_existing_partners(self):
        """Create OUs for existing top-level company partners. Called from data/init_data.xml."""
        partners = self.env["res.partner"].search(
            [
                ("is_company", "=", True),
                ("parent_id", "=", False),
            ]
        )
        created_count = 0
        for partner in partners:
            existing = self.search([("owner_id", "=", partner.id)], limit=1)
            if not existing:
                self.create(
                    {
                        "name": partner.name,
                        "owner_id": partner.id,
                        "user_id": partner.user_id.id if partner.user_id else False,
                    }
                )
                created_count += 1
        if created_count:
            import logging

            logging.getLogger(__name__).info(
                f"Created {created_count} Organizational Units for existing partners."
            )

    @api.model
    def _cron_refresh_metrics(self):
        """Nightly cron to refresh all OU metrics."""
        all_ous = self.search([])
        for ou in all_ous:
            ou._compute_sales_metrics()
            ou._compute_rolling_12m_metrics()
            ou._compute_quotation_metrics()
            ou._compute_order_metrics()
            ou._compute_opportunity_metrics()

    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)
    owner_id = fields.Many2one(
        "res.partner",
        string="Owning Partner",
        domain="[('is_company', '=', True), ('parent_id', '=', False)]",
        ondelete="cascade",
        tracking=True,
        help="The top-level company partner that owns this account.",
    )
    parent_id = fields.Many2one(
        "organizational.unit",
        string="Parent Account",
        ondelete="cascade",
        tracking=True,
    )
    child_ids = fields.One2many(
        "organizational.unit",
        "parent_id",
        string="Child Accounts",
    )
    member_ids = fields.Many2many(
        "res.partner",
        string="Explicit Members",
        help="Contacts or addresses explicitly added to this account.",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Account Manager",
        compute="_compute_user_id",
        inverse="_inverse_user_id",
        store=True,
        readonly=False,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # --- Address (AC1): readonly, sourced from the owning partner ---
    # Related, non-stored fields auto-track the owner's address changes and need
    # no migration/data. Surfaced readonly on the dashboard "Account Details".
    owner_street = fields.Char(
        string="Street", related="owner_id.street", readonly=True
    )
    owner_street2 = fields.Char(
        string="Street 2", related="owner_id.street2", readonly=True
    )
    owner_city = fields.Char(
        string="City", related="owner_id.city", readonly=True
    )
    owner_state_id = fields.Many2one(
        "res.country.state",
        string="State",
        related="owner_id.state_id",
        readonly=True,
    )
    owner_zip = fields.Char(
        string="ZIP", related="owner_id.zip", readonly=True
    )
    owner_country_id = fields.Many2one(
        "res.country",
        string="Country",
        related="owner_id.country_id",
        readonly=True,
    )

    # Computed metrics for dashboard
    # Note: stored=True allows searching/sorting. Recomputed when owner/member/child changes
    # or when related invoices/orders/opportunities change.
    ytd_sales = fields.Monetary(
        string="YTD Sales",
        compute="_compute_sales_metrics",
        store=True,
        currency_field="currency_id",
    )
    ytd_sales_prior_year = fields.Monetary(
        string="YTD Sales (Prior Year)",
        compute="_compute_sales_metrics",
        store=True,
        currency_field="currency_id",
    )
    ytd_sales_change_pct = fields.Float(
        string="YTD Sales Change %",
        compute="_compute_sales_metrics",
        store=True,
    )
    rolling_12m_sales = fields.Monetary(
        string="Rolling 12M Sales",
        compute="_compute_rolling_12m_metrics",
        currency_field="currency_id",
    )
    rolling_12m_sales_prior = fields.Monetary(
        string="Rolling 12M Sales (Prior)",
        compute="_compute_rolling_12m_metrics",
        currency_field="currency_id",
    )
    rolling_12m_change_pct = fields.Float(
        string="Rolling 12M Change %",
        compute="_compute_rolling_12m_metrics",
    )
    open_quotations_count = fields.Integer(
        string="Open Quotations",
        compute="_compute_quotation_metrics",
        store=True,
    )
    open_quotations_amount = fields.Monetary(
        string="Open Quotations Amount",
        compute="_compute_quotation_metrics",
        store=True,
        currency_field="currency_id",
    )
    won_quotations_count = fields.Integer(
        string="Won Quotations (YTD)",
        compute="_compute_quotation_metrics",
        store=True,
    )
    won_quotations_amount = fields.Monetary(
        string="Won Quotations Amount (YTD)",
        compute="_compute_quotation_metrics",
        store=True,
        currency_field="currency_id",
    )
    open_orders_count = fields.Integer(
        string="Open Orders",
        compute="_compute_order_metrics",
        store=True,
    )
    open_orders_amount = fields.Monetary(
        string="Open Orders Amount",
        compute="_compute_order_metrics",
        store=True,
        currency_field="currency_id",
    )
    open_orders_to_invoice_amount = fields.Monetary(
        string="To Invoice",
        compute="_compute_order_metrics",
        store=True,
        currency_field="currency_id",
    )
    open_opportunities_count = fields.Integer(
        string="Open Opportunities",
        compute="_compute_opportunity_metrics",
        store=True,
    )
    open_opportunities_amount = fields.Monetary(
        string="Open Opportunities Amount",
        compute="_compute_opportunity_metrics",
        store=True,
        currency_field="currency_id",
    )
    won_opportunities_count = fields.Integer(
        string="Won Opportunities (YTD)",
        compute="_compute_opportunity_metrics",
        store=True,
    )
    won_opportunities_amount = fields.Monetary(
        string="Won Opportunities Amount (YTD)",
        compute="_compute_opportunity_metrics",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    fiscal_year_start_date = fields.Date(
        string="Fiscal Year Start Date",
        help="Custom fiscal year start date for this account. Overrides company default.",
    )
    avg_gross_profit_percentage = fields.Float(
        string="Avg Gross Profit %",
        compute="_compute_gross_profit_metrics",
    )
    all_ou_avg_gross_profit_percentage = fields.Float(
        string="Avg GP % (all OUs)",
        compute="_compute_all_ou_gross_profit_metrics",
        help="Revenue-weighted average gross-profit margin across ALL "
        "organizational units' YTD posted customer invoices "
        "(sum(revenue - cost) / sum(revenue)). The same comparison figure "
        "appears on every OU, to benchmark this account's own Avg Gross "
        "Profit %.",
    )
    won_quotations_prior_count = fields.Integer(
        string="Bookings Prior (Count)",
        compute="_compute_quotation_metrics",
        store=True,
    )
    won_quotations_prior_amount = fields.Monetary(
        string="Bookings Prior (Amount)",
        compute="_compute_quotation_metrics",
        store=True,
        currency_field="currency_id",
    )
    open_orders_late_count = fields.Integer(
        string="Late Orders",
        compute="_compute_order_metrics",
        store=True,
    )
    open_orders_late_amount = fields.Monetary(
        string="Late Orders Amount",
        compute="_compute_order_metrics",
        store=True,
        currency_field="currency_id",
    )
    open_orders_ontime_count = fields.Integer(
        string="On-Time Orders",
        compute="_compute_order_metrics",
        store=True,
    )
    open_orders_ontime_amount = fields.Monetary(
        string="On-Time Orders Amount",
        compute="_compute_order_metrics",
        store=True,
        currency_field="currency_id",
    )
    last_sale_order_date = fields.Date(
        string="Last Sales Order",
        compute="_compute_order_metrics",
        store=True,
    )

    @api.depends(
        "owner_id",
        "member_ids",
        "child_ids",
        "fiscal_year_start_date",
        "owner_id.invoice_ids.state",
        "owner_id.invoice_ids.amount_total",
        "owner_id.invoice_ids.invoice_date",
        "owner_id.invoice_ids.move_type",
        "owner_id.invoice_ids.currency_id",
    )
    def _compute_gross_profit_metrics(self):
        for record in self:
            partners = record._get_all_partners()
            if not partners:
                record.avg_gross_profit_percentage = 0.0
                continue

            invoices = record._get_ytd_gross_profit_invoices(partners)

            if not invoices:
                record.avg_gross_profit_percentage = 0.0
                continue

            invoice_margins = []
            for inv in invoices:
                total_revenue, total_cost = self._invoice_revenue_cost(inv)
                if not total_revenue:
                    continue
                invoice_margins.append((total_revenue - total_cost) / total_revenue)

            record.avg_gross_profit_percentage = (
                sum(invoice_margins) / len(invoice_margins) if invoice_margins else 0.0
            )

    def _get_ytd_gross_profit_invoices(self, partners):
        """Return the posted YTD customer invoices for ``partners``.

        Shared search domain used by both the per-OU
        ``avg_gross_profit_percentage`` compute and the all-OU comparison
        figure, so the two metrics stay consistent.
        """
        self.ensure_one()
        if not partners:
            return self.env["account.move"]
        start_ytd, end_ytd = self._get_ytd_dates()
        return self.env["account.move"].search(
            [
                ("partner_id", "in", partners.ids),
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("invoice_date", ">=", start_ytd),
                ("invoice_date", "<=", end_ytd),
            ]
        )

    def _invoice_revenue_cost(self, inv):
        """Return ``(revenue, cost)`` for a single customer invoice, both in
        company currency.

        Revenue (``price_subtotal``) is denominated in the invoice currency
        while cost (``standard_price``) is already in company currency.
        Convert the revenue to company currency at the invoice date before
        differencing so foreign-currency-billed invoices don't manufacture a
        fake margin equal to the FX rate.  ``_convert`` short-circuits to
        identity when source and target currencies match (single-currency
        invoices are unaffected); cost is left as-is since it is
        company-currency already.

        This is the single source of the revenue/cost derivation reused by
        both ``avg_gross_profit_percentage`` (per-OU, unweighted mean of
        per-invoice margins) and ``all_ou_avg_gross_profit_percentage``
        (revenue-weighted across all OUs).
        """
        product_lines = inv.invoice_line_ids.filtered("product_id")
        company = inv.company_id or self.env.company
        company_currency = company.currency_id
        conv_date = inv.invoice_date or inv.date or fields.Date.context_today(inv)
        invoice_currency = inv.currency_id or company_currency
        total_revenue = invoice_currency._convert(
            sum(product_lines.mapped("price_subtotal")),
            company_currency,
            company,
            conv_date,
        )
        total_cost = sum(
            line.quantity * (line.product_id.standard_price or 0.0)
            for line in product_lines
        )
        return total_revenue, total_cost

    @api.depends(
        "owner_id",
        "member_ids",
        "child_ids",
        "fiscal_year_start_date",
        "owner_id.invoice_ids.state",
        "owner_id.invoice_ids.amount_total",
        "owner_id.invoice_ids.invoice_date",
        "owner_id.invoice_ids.move_type",
        "owner_id.invoice_ids.currency_id",
    )
    def _compute_all_ou_gross_profit_metrics(self):
        """Revenue-weighted all-OU average gross-profit %.

        A single rolled-up figure -- ``sum(revenue - cost) / sum(revenue)``
        across every OU's YTD posted customer invoices -- so the SAME value
        lands on every OU record.  Provides a benchmark to compare an
        individual OU's ``avg_gross_profit_percentage`` against.  Reuses the
        same invoice domain and per-invoice revenue/cost derivation as the
        per-OU compute (``_get_ytd_gross_profit_invoices`` /
        ``_invoice_revenue_cost``) so the two metrics stay consistent.
        """
        all_value = self._get_all_ou_avg_gross_profit_percentage()
        for record in self:
            record.all_ou_avg_gross_profit_percentage = all_value

    @api.model
    def _get_all_ou_avg_gross_profit_percentage(self):
        """Compute the revenue-weighted GP% across ALL OUs' YTD invoices."""
        total_revenue = 0.0
        total_cost = 0.0
        # Collect every OU's YTD invoices once (de-duplicated -- a partner that
        # belongs to several OUs, e.g. via parent/child hierarchies, must not
        # have its invoices counted twice in the rolled-up figure).
        all_invoices = self.env["account.move"]
        for ou in self.search([]):
            partners = ou._get_all_partners()
            if not partners:
                continue
            all_invoices |= ou._get_ytd_gross_profit_invoices(partners)
        for inv in all_invoices:
            revenue, cost = self._invoice_revenue_cost(inv)
            total_revenue += revenue
            total_cost += cost
        if not total_revenue:
            return 0.0
        return (total_revenue - total_cost) / total_revenue

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.user_id:
                record.message_subscribe(partner_ids=[record.user_id.partner_id.id])
        return records

    def write(self, vals):
        res = super().write(vals)
        if "user_id" in vals and vals.get("user_id"):
            user = self.env["res.users"].browse(vals["user_id"])
            if user:
                self.message_subscribe(partner_ids=[user.partner_id.id])
        return res

    @api.depends("owner_id.user_id")
    def _compute_user_id(self):
        for ou in self:
            if ou.owner_id:
                ou.user_id = ou.owner_id.user_id
            else:
                ou.user_id = ou.user_id

    def _inverse_user_id(self):
        pass

    @api.constrains("owner_id", "parent_id")
    def _check_owner_or_parent(self):
        for record in self:
            if not record.owner_id and not record.parent_id:
                raise ValidationError(
                    _(
                        "An organizational unit must have either an owning partner or a parent account."
                    )
                )

    @api.constrains("parent_id")
    def _check_parent_recursion(self):
        if self._has_cycle():
            raise ValidationError(_("You cannot create recursive account hierarchies."))

    def _get_all_partners(self):
        """Get all partners associated with this account, including from child accounts."""
        self.ensure_one()
        partners = self.env["res.partner"]

        # Add owning partner and its children (contacts/addresses)
        if self.owner_id:
            partners |= self.owner_id
            partners |= self.owner_id.child_ids

        # Add explicit members
        partners |= self.member_ids

        # Recursively add partners from child accounts
        for child in self.child_ids:
            partners |= child._get_all_partners()

        return partners

    def _get_fiscal_year_start(self, for_date=None):
        """Get the start of the fiscal year for the given date (or today).

        Per-OU fiscal_year_start_date overrides the company default when set.
        """
        if for_date is None:
            for_date = date.today()

        # Per-OU override takes precedence over company settings
        if self.fiscal_year_start_date:
            fy_start = self.fiscal_year_start_date
            candidate = date(for_date.year, fy_start.month, fy_start.day)
            if candidate > for_date:
                candidate = date(for_date.year - 1, fy_start.month, fy_start.day)
            return candidate

        company = self.company_id or self.env.company
        # Get fiscal year month/day from company (defaults to Jan 1 if not set)
        fiscal_month = company.fiscalyear_last_month
        fiscal_day = company.fiscalyear_last_day
        if fiscal_month and fiscal_day:
            # Fiscal year END is fiscal_month/fiscal_day, so START is the day after
            # e.g., if fiscal year ends March 31, it starts April 1
            fiscal_end_month = int(fiscal_month)
            fiscal_end_day = fiscal_day
            # Calculate fiscal year start (day after fiscal year end)
            if fiscal_end_month == 12 and fiscal_end_day == 31:
                # Calendar year
                fiscal_start_month, fiscal_start_day = 1, 1
            else:
                # Day after fiscal year end
                fiscal_end = date(for_date.year, fiscal_end_month, fiscal_end_day)
                fiscal_start = fiscal_end + relativedelta(days=1)
                fiscal_start_month, fiscal_start_day = (
                    fiscal_start.month,
                    fiscal_start.day,
                )
        else:
            # Default to calendar year
            fiscal_start_month, fiscal_start_day = 1, 1

        # Determine which fiscal year we're in
        fiscal_start_this_year = date(
            for_date.year, fiscal_start_month, fiscal_start_day
        )
        if for_date >= fiscal_start_this_year:
            return fiscal_start_this_year
        else:
            return date(for_date.year - 1, fiscal_start_month, fiscal_start_day)

    def _get_ytd_dates(self):
        """Return start of fiscal year and today for YTD calculations."""
        today = date.today()
        start_of_fiscal_year = self._get_fiscal_year_start(today)
        return start_of_fiscal_year, today

    def _get_prior_ytd_dates(self):
        """Return start of prior fiscal year and same day last year for prior YTD calculations."""
        today = date.today()
        same_day_prior_year = today - relativedelta(years=1)
        start_of_prior_fiscal_year = self._get_fiscal_year_start(same_day_prior_year)
        return start_of_prior_fiscal_year, same_day_prior_year

    def _get_calendar_ytd_dates(self):
        """Return (Jan 1 of the current calendar year, today) for calendar-YTD."""
        today = date.today()
        return date(today.year, 1, 1), today

    def _get_prior_calendar_ytd_dates(self):
        """Return (Jan 1 of the prior calendar year, same month/day last year)."""
        today = date.today()
        same_day_prior_year = today - relativedelta(years=1)
        return date(today.year - 1, 1, 1), same_day_prior_year

    @api.model
    def _get_ytd_metric_basis(self):
        """Return the system-wide dashboard YTD basis ('fiscal' or 'bookings').

        Stored as the ``ir.config_parameter``
        ``crm_account_management.ytd_metric_basis``; absent/empty is treated as
        ``'fiscal'`` (the default, no-regression behaviour).
        """
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("crm_account_management.ytd_metric_basis", "fiscal")
            or "fiscal"
        )

    @api.depends(
        "owner_id",
        "member_ids",
        "child_ids",
        "fiscal_year_start_date",
        "owner_id.invoice_ids.state",
        "owner_id.invoice_ids.amount_total",
        "owner_id.invoice_ids.invoice_date",
        "owner_id.invoice_ids.move_type",
        "owner_id.invoice_ids.currency_id",
        "owner_id.sale_order_ids.state",
        "owner_id.sale_order_ids.amount_total",
        "owner_id.sale_order_ids.date_order",
        "owner_id.sale_order_ids.currency_id",
    )
    def _compute_sales_metrics(self):
        basis = self._get_ytd_metric_basis()
        for record in self:
            partners = record._get_all_partners()
            if not partners:
                record.ytd_sales = 0.0
                record.ytd_sales_prior_year = 0.0
                record.ytd_sales_change_pct = 0.0
                continue

            if basis == "bookings":
                # Calendar-YTD bookings: confirmed sale orders (state='sale')
                # over the calendar window, FX-converted via _sum_in_currency
                # (the same aggregation _compute_quotation_metrics uses).
                start_ytd, end_ytd = record._get_calendar_ytd_dates()
                start_prior, end_prior = record._get_prior_calendar_ytd_dates()

                ytd_orders = self.env["sale.order"].search(
                    [
                        ("partner_id", "in", partners.ids),
                        ("state", "=", "sale"),
                        ("date_order", ">=", start_ytd),
                        ("date_order", "<=", end_ytd),
                    ]
                )
                record.ytd_sales = record._sum_in_currency(
                    ytd_orders, "amount_total", "date_order"
                )

                prior_orders = self.env["sale.order"].search(
                    [
                        ("partner_id", "in", partners.ids),
                        ("state", "=", "sale"),
                        ("date_order", ">=", start_prior),
                        ("date_order", "<=", end_prior),
                    ]
                )
                record.ytd_sales_prior_year = record._sum_in_currency(
                    prior_orders, "amount_total", "date_order"
                )
            else:
                start_ytd, end_ytd = record._get_ytd_dates()
                start_prior, end_prior = record._get_prior_ytd_dates()

                # YTD sales from confirmed invoices
                ytd_invoices = self.env["account.move"].search(
                    [
                        ("partner_id", "in", partners.ids),
                        ("move_type", "in", ["out_invoice", "out_refund"]),
                        ("state", "=", "posted"),
                        ("invoice_date", ">=", start_ytd),
                        ("invoice_date", "<=", end_ytd),
                    ]
                )
                record.ytd_sales = record._sum_invoices_in_currency(ytd_invoices)

                # Prior YTD sales
                prior_invoices = self.env["account.move"].search(
                    [
                        ("partner_id", "in", partners.ids),
                        ("move_type", "in", ["out_invoice", "out_refund"]),
                        ("state", "=", "posted"),
                        ("invoice_date", ">=", start_prior),
                        ("invoice_date", "<=", end_prior),
                    ]
                )
                record.ytd_sales_prior_year = record._sum_invoices_in_currency(
                    prior_invoices
                )

            # Calculate YTD change percentage (as decimal for percentage widget: 0.5 = 50%)
            if record.ytd_sales_prior_year:
                record.ytd_sales_change_pct = (
                    record.ytd_sales - record.ytd_sales_prior_year
                ) / record.ytd_sales_prior_year
            else:
                record.ytd_sales_change_pct = 0.0 if not record.ytd_sales else 1.0

    @api.depends(
        "owner_id",
        "member_ids",
        "child_ids",
        "owner_id.sale_order_ids.state",
        "owner_id.sale_order_ids.amount_total",
        "owner_id.sale_order_ids.date_order",
        "owner_id.sale_order_ids.currency_id",
    )
    def _compute_rolling_12m_metrics(self):
        """Rolling 12M bookings metrics - not stored since date range shifts daily.

        Bookings = confirmed ``sale.order`` (``state == "sale"``) aggregated by
        ``date_order`` via ``_sum_in_currency`` (which converts mixed currencies
        at each order's ``date_order`` rate). Windows are half-open
        (``> start`` / ``<= end``) so the 12-month seam is never double-counted.
        """
        for record in self:
            partners = record._get_all_partners()
            if not partners:
                record.rolling_12m_sales = 0.0
                record.rolling_12m_sales_prior = 0.0
                record.rolling_12m_change_pct = 0.0
                continue

            today = date.today()
            rolling_12m_start = today - relativedelta(months=12)
            rolling_12m_orders = self.env["sale.order"].search(
                [
                    ("partner_id", "in", partners.ids),
                    ("state", "=", "sale"),
                    ("date_order", ">", rolling_12m_start),
                    ("date_order", "<=", today),
                ]
            )
            record.rolling_12m_sales = record._sum_in_currency(
                rolling_12m_orders, "amount_total", "date_order"
            )

            # Prior rolling 12 months (12-24 months ago)
            rolling_prior_start = today - relativedelta(months=24)
            rolling_prior_end = today - relativedelta(months=12)
            rolling_prior_orders = self.env["sale.order"].search(
                [
                    ("partner_id", "in", partners.ids),
                    ("state", "=", "sale"),
                    ("date_order", ">", rolling_prior_start),
                    ("date_order", "<=", rolling_prior_end),
                ]
            )
            record.rolling_12m_sales_prior = record._sum_in_currency(
                rolling_prior_orders, "amount_total", "date_order"
            )

            # Calculate rolling 12m change percentage
            if record.rolling_12m_sales_prior:
                record.rolling_12m_change_pct = (
                    record.rolling_12m_sales - record.rolling_12m_sales_prior
                ) / record.rolling_12m_sales_prior
            else:
                record.rolling_12m_change_pct = (
                    0.0 if not record.rolling_12m_sales else 1.0
                )

    @api.depends(
        "owner_id",
        "member_ids",
        "child_ids",
        "fiscal_year_start_date",
        "owner_id.sale_order_ids.state",
        "owner_id.sale_order_ids.amount_total",
        "owner_id.sale_order_ids.date_order",
        "owner_id.sale_order_ids.currency_id",
    )
    def _compute_quotation_metrics(self):
        for record in self:
            partners = record._get_all_partners()
            if not partners:
                record.open_quotations_count = 0
                record.open_quotations_amount = 0.0
                record.won_quotations_count = 0
                record.won_quotations_amount = 0.0
                record.won_quotations_prior_count = 0
                record.won_quotations_prior_amount = 0.0
                continue

            start_ytd, end_ytd = record._get_ytd_dates()
            start_prior, end_prior = record._get_prior_ytd_dates()

            # Open quotations (draft/sent)
            open_quotes = self.env["sale.order"].search(
                [
                    ("partner_id", "in", partners.ids),
                    ("state", "in", ["draft", "sent"]),
                ]
            )
            record.open_quotations_count = len(open_quotes)
            record.open_quotations_amount = record._sum_in_currency(
                open_quotes, "amount_total", "date_order"
            )

            # Won quotations YTD (confirmed this year)
            won_quotes = self.env["sale.order"].search(
                [
                    ("partner_id", "in", partners.ids),
                    ("state", "=", "sale"),
                    ("date_order", ">=", start_ytd),
                    ("date_order", "<=", end_ytd),
                ]
            )
            record.won_quotations_count = len(won_quotes)
            record.won_quotations_amount = record._sum_in_currency(
                won_quotes, "amount_total", "date_order"
            )

            # Won quotations prior YTD
            won_quotes_prior = self.env["sale.order"].search(
                [
                    ("partner_id", "in", partners.ids),
                    ("state", "=", "sale"),
                    ("date_order", ">=", start_prior),
                    ("date_order", "<=", end_prior),
                ]
            )
            record.won_quotations_prior_count = len(won_quotes_prior)
            record.won_quotations_prior_amount = record._sum_in_currency(
                won_quotes_prior, "amount_total", "date_order"
            )

    @api.depends(
        "owner_id",
        "member_ids",
        "child_ids",
        "owner_id.sale_order_ids.state",
        "owner_id.sale_order_ids.amount_total",
        "owner_id.sale_order_ids.invoice_status",
        "owner_id.sale_order_ids.delivery_status",
        "owner_id.sale_order_ids.commitment_date",
        "owner_id.sale_order_ids.expected_date",
        "owner_id.sale_order_ids.date_order",
        "owner_id.sale_order_ids.currency_id",
        "owner_id.sale_order_ids.invoice_ids.state",
        "owner_id.sale_order_ids.invoice_ids.amount_total",
        "owner_id.sale_order_ids.invoice_ids.move_type",
    )
    def _compute_order_metrics(self):
        today = date.today()
        for record in self:
            partners = record._get_all_partners()
            if not partners:
                record.open_orders_count = 0
                record.open_orders_amount = 0.0
                record.open_orders_to_invoice_amount = 0.0
                record.open_orders_late_count = 0
                record.open_orders_late_amount = 0.0
                record.open_orders_ontime_count = 0
                record.open_orders_ontime_amount = 0.0
                record.last_sale_order_date = False
                continue

            # Open orders (confirmed but not fully delivered AND invoiced)
            open_orders = self.env["sale.order"].search(
                [
                    ("partner_id", "in", partners.ids),
                    ("state", "=", "sale"),
                    "|",
                    ("invoice_status", "!=", "invoiced"),
                    ("delivery_status", "not in", ["full", False]),
                ]
            )
            record.open_orders_count = len(open_orders)
            record.open_orders_amount = record._sum_in_currency(
                open_orders, "amount_total", "date_order"
            )

            to_invoice = 0.0
            late_count = 0
            late_amount = 0.0
            ontime_count = 0
            ontime_amount = 0.0
            company = record.company_id or record.env.company
            target = record.currency_id
            for order in open_orders:
                order_date = order.date_order.date() if order.date_order else today
                order_amount_converted = order.currency_id._convert(
                    order.amount_total, target, company, order_date
                )
                # Each posted invoice's amount_total is in that invoice's own
                # currency_id (NOT the order or company currency), so convert
                # each move from its own currency at its own accounting date
                # before subtracting from the converted order amount.
                posted_invoices = order.invoice_ids.filtered(
                    lambda m: m.state == "posted"
                )
                invoiced_converted = record._sum_invoices_in_currency(posted_invoices)
                to_invoice += max(0.0, order_amount_converted - invoiced_converted)
                # Late vs on-time: use commitment_date if set, else expected_date
                due = order.commitment_date or order.expected_date
                if due and due.date() < today:
                    late_count += 1
                    late_amount += order_amount_converted
                else:
                    ontime_count += 1
                    ontime_amount += order_amount_converted
            record.open_orders_to_invoice_amount = to_invoice
            record.open_orders_late_count = late_count
            record.open_orders_late_amount = late_amount
            record.open_orders_ontime_count = ontime_count
            record.open_orders_ontime_amount = ontime_amount

            # Last sale order date
            last_order = self.env["sale.order"].search(
                [
                    ("partner_id", "in", partners.ids),
                    ("state", "=", "sale"),
                ],
                order="date_order desc",
                limit=1,
            )
            record.last_sale_order_date = (
                last_order.date_order.date() if last_order else False
            )

    @api.depends(
        "owner_id",
        "member_ids",
        "child_ids",
        "fiscal_year_start_date",
        "owner_id.opportunity_ids.probability",
        "owner_id.opportunity_ids.expected_revenue",
        "owner_id.opportunity_ids.date_closed",
        "owner_id.opportunity_ids.company_currency",
    )
    def _compute_opportunity_metrics(self):
        for record in self:
            partners = record._get_all_partners()
            if not partners:
                record.open_opportunities_count = 0
                record.open_opportunities_amount = 0.0
                record.won_opportunities_count = 0
                record.won_opportunities_amount = 0.0
                continue

            start_ytd, end_ytd = record._get_ytd_dates()

            # Open opportunities
            open_opps = self.env["crm.lead"].search(
                [
                    ("partner_id", "in", partners.ids),
                    ("type", "=", "opportunity"),
                    ("probability", "<", 100),
                    ("probability", ">", 0),
                ]
            )
            record.open_opportunities_count = len(open_opps)
            record.open_opportunities_amount = record._sum_in_currency(
                open_opps, "expected_revenue", "date_closed"
            )

            # Won opportunities YTD
            won_opps = self.env["crm.lead"].search(
                [
                    ("partner_id", "in", partners.ids),
                    ("type", "=", "opportunity"),
                    ("probability", "=", 100),
                    ("date_closed", ">=", start_ytd),
                    ("date_closed", "<=", end_ytd),
                ]
            )
            record.won_opportunities_count = len(won_opps)
            record.won_opportunities_amount = record._sum_in_currency(
                won_opps, "expected_revenue", "date_closed"
            )

    def get_top_products(self, limit=10, date_from=None, date_to=None, sort_by="total_amount"):
        """Get top products purchased by this account.

        Aggregation runs in PostgreSQL via ``_read_group`` over
        ``sale.order.line``, grouped by ``product_id``. The aggregated
        rows are then enriched with the product template id, name and
        ``default_code`` in a single batched read so the call scales to
        thousands of order lines without prefetching every record.
        """
        self.ensure_one()
        partners = self._get_all_partners()
        if not partners:
            return []

        if not date_to:
            date_to = date.today()

        domain = [
            ("order_id.partner_id", "in", partners.ids),
            ("order_id.state", "=", "sale"),
            ("order_id.date_order", "<=", date_to),
        ]
        if date_from:
            domain.append(("order_id.date_order", ">=", date_from))

        # PostgreSQL-side aggregation: avoids reading thousands of SOLs
        # into memory and respects sale.order.line record rules through
        # the ORM's standard read_group implementation.
        groups = self.env["sale.order.line"]._read_group(
            domain,
            groupby=["product_id"],
            aggregates=["product_uom_qty:sum", "price_subtotal:sum"],
        )

        product_ids = [p.id for p, _qty, _amt in groups if p]
        if not product_ids:
            return []

        # Single batched fetch of presentation fields. Using sudo on the
        # product read is safe — access to the line was already enforced
        # by _read_group above; we are only resolving display attributes.
        products = self.env["product.product"].browse(product_ids).sudo()
        product_info = {
            p.id: {
                "tmpl_id": p.product_tmpl_id.id,
                "name": p.display_name or p.name or "",
                "default_code": p.default_code or "",
            }
            for p in products
        }

        # Roll up variants under their template (preserves the legacy
        # behaviour where ``product_id`` in the returned dict refers to
        # ``product.template`` and variants are merged).
        by_tmpl = {}
        for product, qty, amount in groups:
            if not product:
                continue
            info = product_info.get(product.id)
            if not info:
                continue
            tmpl_id = info["tmpl_id"]
            entry = by_tmpl.get(tmpl_id)
            if entry is None:
                by_tmpl[tmpl_id] = {
                    "product_id": tmpl_id,
                    "product_name": info["name"],
                    "default_code": info["default_code"],
                    "total_qty": qty or 0.0,
                    "total_amount": amount or 0.0,
                }
            else:
                entry["total_qty"] += qty or 0.0
                entry["total_amount"] += amount or 0.0
        product_data = list(by_tmpl.values())

        if sort_by == "default_code":
            product_data.sort(key=lambda x: x["default_code"] or "")
        elif sort_by == "product_name":
            product_data.sort(key=lambda x: x["product_name"] or "")
        elif sort_by == "total_qty":
            product_data.sort(key=lambda x: x["total_qty"], reverse=True)
        else:
            product_data.sort(key=lambda x: x["total_amount"], reverse=True)

        if limit is None:
            return product_data
        return product_data[:limit]

    def get_sales_by_period(self, period="month", periods=12, date_from=None, date_to=None):
        """Get sales data by period for trend analysis."""
        self.ensure_one()
        partners = self._get_all_partners()
        if not partners:
            return []

        today = date.today()

        if period == "month":
            date_trunc = "month"
            delta = relativedelta(months=1)
        elif period == "year":
            date_trunc = "year"
            delta = relativedelta(years=1)
        else:  # quarter
            date_trunc = "quarter"
            delta = relativedelta(months=3)

        if date_from is None:
            date_from = today - (delta * periods)
        if date_to is None:
            date_to = today

        # Group by (period, currency) so mixed-currency invoices can be
        # converted to the OU currency before being summed into one period
        # total. Summing am.amount_total across currencies in raw SQL would add
        # e.g. USD + CAD numerically, the same bug fixed in the metric computes.
        query = """
            SELECT
                DATE_TRUNC(%s, am.invoice_date) as period,
                am.currency_id as currency_id,
                SUM(CASE WHEN am.move_type = 'out_invoice' THEN am.amount_total
                         ELSE -am.amount_total END) as total
            FROM account_move am
            WHERE am.partner_id IN %s
              AND am.move_type IN ('out_invoice', 'out_refund')
              AND am.state = 'posted'
              AND am.invoice_date >= %s
              AND am.invoice_date <= %s
            GROUP BY DATE_TRUNC(%s, am.invoice_date), am.currency_id
            ORDER BY period
        """
        self.env.cr.execute(
            query, (date_trunc, tuple(partners.ids), date_from, date_to, date_trunc)
        )
        rows = self.env.cr.dictfetchall()

        target = self.currency_id
        company = self.company_id or self.env.company
        currency_model = self.env["res.currency"]
        period_totals = {}
        for row in rows:
            period = row["period"]
            amount = row["total"] or 0.0
            source = (
                currency_model.browse(row["currency_id"])
                if row.get("currency_id")
                else target
            )
            # Convert each currency bucket at the period date so the period
            # total is expressed in the OU currency.
            conv_date = period.date() if hasattr(period, "date") else period
            converted = source._convert(amount, target, company, conv_date or today)
            period_totals[period] = period_totals.get(period, 0.0) + converted

        return [
            {"period": period, "total": period_totals[period]}
            for period in sorted(period_totals)
        ]

    def action_view_quotations(self):
        """Open quotations for this account."""
        self.ensure_one()
        partners = self._get_all_partners()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quotations"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "in", partners.ids),
                ("state", "in", ["draft", "sent"]),
            ],
            "context": {
                "default_partner_id": self.owner_id.id if self.owner_id else False
            },
        }

    def action_view_orders(self):
        """Open open sales orders for this account (matching dashboard metric)."""
        self.ensure_one()
        partners = self._get_all_partners()
        return {
            "type": "ir.actions.act_window",
            "name": _("Open Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "in", partners.ids),
                ("state", "=", "sale"),
                "|",
                ("invoice_status", "!=", "invoiced"),
                ("delivery_status", "not in", ["full", False]),
            ],
            "context": {
                "default_partner_id": self.owner_id.id if self.owner_id else False
            },
        }

    def action_view_opportunities(self):
        """Open opportunities for this account."""
        self.ensure_one()
        partners = self._get_all_partners()
        return {
            "type": "ir.actions.act_window",
            "name": _("Opportunities"),
            "res_model": "crm.lead",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "in", partners.ids),
                ("type", "=", "opportunity"),
            ],
            "context": {
                "default_partner_id": self.owner_id.id if self.owner_id else False
            },
        }

    def _get_invoice_action(self, name, extra_domain=None):
        """Return the standard customer invoices action with extra domain filters."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "account.action_move_out_invoice_type"
        )
        partners = self._get_all_partners()
        domain = [("partner_id", "in", partners.ids)]
        if extra_domain:
            domain += extra_domain
        action["name"] = name
        action["domain"] = domain
        ctx = action.get("context", {})
        if isinstance(ctx, str):
            ctx = dict(safe_eval(ctx))
        ctx["default_partner_id"] = self.owner_id.id if self.owner_id else False
        action["context"] = ctx
        return action

    def action_view_invoices(self):
        """Open invoices for this account."""
        return self._get_invoice_action(_("Invoices"))

    def action_view_invoices_ytd(self):
        """Open posted invoices for this account in the current fiscal YTD range."""
        start_ytd, end_ytd = self._get_ytd_dates()
        return self._get_invoice_action(_("YTD Invoices"), [
            ("state", "=", "posted"),
            ("invoice_date", ">=", start_ytd),
            ("invoice_date", "<=", end_ytd),
        ])

    def action_view_invoices_prior_ytd(self):
        """Open posted invoices for this account in the prior fiscal YTD range."""
        start_prior, end_prior = self._get_prior_ytd_dates()
        return self._get_invoice_action(_("Prior YTD Invoices"), [
            ("state", "=", "posted"),
            ("invoice_date", ">=", start_prior),
            ("invoice_date", "<=", end_prior),
        ])

    def action_view_orders_rolling_12m(self):
        """Open confirmed sale orders (bookings) for this account from the last 12 months."""
        self.ensure_one()
        partners = self._get_all_partners()
        today = date.today()
        date_from = today - relativedelta(months=12)
        return {
            "type": "ir.actions.act_window",
            "name": _("Bookings (Last 12 Months)"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "in", partners.ids),
                ("state", "=", "sale"),
                ("date_order", ">", date_from),
                ("date_order", "<=", today),
            ],
            "context": {"default_partner_id": self.owner_id.id if self.owner_id else False},
        }

    def action_view_orders_prior_rolling_12m(self):
        """Open confirmed sale orders (bookings) for this account from 13–24 months ago."""
        self.ensure_one()
        partners = self._get_all_partners()
        today = date.today()
        date_from = today - relativedelta(months=24)
        date_to = today - relativedelta(months=12)
        return {
            "type": "ir.actions.act_window",
            "name": _("Bookings (Prior 12 Months)"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "in", partners.ids),
                ("state", "=", "sale"),
                ("date_order", ">", date_from),
                ("date_order", "<=", date_to),
            ],
            "context": {"default_partner_id": self.owner_id.id if self.owner_id else False},
        }

    def action_view_won_quotations_ytd(self):
        """Open confirmed sale orders (bookings) for the current fiscal YTD."""
        self.ensure_one()
        partners = self._get_all_partners()
        start_ytd, end_ytd = self._get_ytd_dates()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bookings (YTD)"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "in", partners.ids),
                ("state", "=", "sale"),
                ("date_order", ">=", start_ytd),
                ("date_order", "<=", end_ytd),
            ],
            "context": {"default_partner_id": self.owner_id.id if self.owner_id else False},
        }

    def _sum_in_currency(self, records, amount_field, date_field):
        """Sum ``amount_field`` on ``records`` converting each value to ``self.currency_id``.

        For each record its own source currency (``record.currency_id`` for
        ``sale.order``, ``record.company_currency`` for ``crm.lead``) is used to
        convert the amount at the exchange rate in effect on the record's
        ``date_field`` date.  When source and target currencies are the same,
        ``_convert`` short-circuits to the identity conversion so the helper is
        safe to call for single-currency sets.

        The conversion date is taken from ``date_field``; if the value is a
        ``Datetime`` its ``.date()`` is used so the rate lookup is date-granular.
        When ``date_field`` is absent or falsy, today's date is used as a
        fallback.

        Note: ``crm.lead.expected_revenue`` is denominated in
        ``company_currency``, which for Pneumac always equals the OU's
        ``currency_id`` (CAD).  Routing it through this helper is therefore a
        no-op in practice but keeps the code path uniform.
        """
        self.ensure_one()
        target = self.currency_id
        company = self.company_id or self.env.company
        today = date.today()
        total = 0.0
        for record in records:
            amount = record[amount_field] or 0.0
            if not amount:
                continue
            # Determine source currency: prefer currency_id, fall back to company_currency
            fields_map = record._fields
            if "currency_id" in fields_map and record.currency_id:
                source = record.currency_id
            elif "company_currency" in fields_map and record.company_currency:
                source = record.company_currency
            else:
                source = target
            raw_date = record[date_field] if date_field else None
            if raw_date and hasattr(raw_date, "date"):
                conv_date = raw_date.date()
            elif raw_date:
                conv_date = raw_date
            else:
                conv_date = today
            total += source._convert(amount, target, company, conv_date)
        return total

    def _sum_invoices_in_currency(self, invoices):
        """Sum customer invoices/refunds, converting each to ``self.currency_id``.

        ``account.move.amount_total`` is denominated in the move's own
        ``currency_id`` (the invoice currency), NOT the company currency, so a
        mixed-currency set (e.g. a USD invoice and a CAD invoice) must be
        converted to a common currency before summing — exactly the same bug
        class fixed for sale orders in :meth:`_sum_in_currency`.

        ``out_refund`` moves are subtracted (they reduce net sales); each move
        is converted from its own currency at its ``invoice_date`` (falling back
        to ``date`` then today when the accounting date is unset).
        """
        self.ensure_one()
        target = self.currency_id
        company = self.company_id or self.env.company
        today = date.today()
        total = 0.0
        for inv in invoices:
            amount = inv.amount_total or 0.0
            if not amount:
                continue
            signed = amount if inv.move_type == "out_invoice" else -amount
            source = inv.currency_id or target
            conv_date = inv.invoice_date or inv.date or today
            total += source._convert(signed, target, company, conv_date)
        return total

    def action_view_won_quotations_prior_ytd(self):
        """Open confirmed sale orders (bookings) for the prior fiscal YTD."""
        self.ensure_one()
        partners = self._get_all_partners()
        start_prior, end_prior = self._get_prior_ytd_dates()
        return {
            "type": "ir.actions.act_window",
            "name": _("Bookings (Prior YTD)"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "in", partners.ids),
                ("state", "=", "sale"),
                ("date_order", ">=", start_prior),
                ("date_order", "<=", end_prior),
            ],
            "context": {"default_partner_id": self.owner_id.id if self.owner_id else False},
        }

    def action_view_orders_late(self):
        """Open late orders (past commitment/expected date)."""
        self.ensure_one()
        partners = self._get_all_partners()
        today = date.today()
        # Find open orders, then filter to late ones
        open_orders = self.env["sale.order"].search(
            [
                ("partner_id", "in", partners.ids),
                ("state", "=", "sale"),
                "|",
                ("invoice_status", "!=", "invoiced"),
                ("delivery_status", "not in", ["full", False]),
            ]
        )
        late_ids = [
            o.id for o in open_orders
            if (o.commitment_date or o.expected_date)
            and (o.commitment_date or o.expected_date).date() < today
        ]
        return {
            "type": "ir.actions.act_window",
            "name": _("Late Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", late_ids)],
            "context": {"default_partner_id": self.owner_id.id if self.owner_id else False},
        }

    def action_view_orders_ontime(self):
        """Open on-time orders (not past commitment/expected date)."""
        self.ensure_one()
        partners = self._get_all_partners()
        today = date.today()
        open_orders = self.env["sale.order"].search(
            [
                ("partner_id", "in", partners.ids),
                ("state", "=", "sale"),
                "|",
                ("invoice_status", "!=", "invoiced"),
                ("delivery_status", "not in", ["full", False]),
            ]
        )
        ontime_ids = [
            o.id for o in open_orders
            if not (o.commitment_date or o.expected_date)
            or (o.commitment_date or o.expected_date).date() >= today
        ]
        return {
            "type": "ir.actions.act_window",
            "name": _("On-Time Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", ontime_ids)],
            "context": {"default_partner_id": self.owner_id.id if self.owner_id else False},
        }

    def action_view_open_opportunities(self):
        """Open the CRM pipeline filtered to open opportunities for this account."""
        self.ensure_one()
        partners = self._get_all_partners()
        return {
            "type": "ir.actions.act_window",
            "name": _("Open Opportunities"),
            "res_model": "crm.lead",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "in", partners.ids),
                ("type", "=", "opportunity"),
                ("probability", ">", 0),
                ("probability", "<", 100),
            ],
            "context": {"default_partner_id": self.owner_id.id if self.owner_id else False},
        }

    def action_view_won_opportunities_ytd(self):
        """Open won opportunities closed in the current fiscal YTD."""
        self.ensure_one()
        partners = self._get_all_partners()
        start_ytd, end_ytd = self._get_ytd_dates()
        return {
            "type": "ir.actions.act_window",
            "name": _("Won Opportunities (YTD)"),
            "res_model": "crm.lead",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "in", partners.ids),
                ("type", "=", "opportunity"),
                ("probability", "=", 100),
                ("date_closed", ">=", start_ytd),
                ("date_closed", "<=", end_ytd),
            ],
            "context": {"default_partner_id": self.owner_id.id if self.owner_id else False},
        }

    def action_view_invoices_period(self, date_from, date_to):
        """Open posted invoices for a specific date range (called from JS chart click)."""
        return self._get_invoice_action(_("Invoices"), [
            ("state", "=", "posted"),
            ("invoice_date", ">=", date_from),
            ("invoice_date", "<=", date_to),
        ])

    def action_view_orders_for_product(self, product_tmpl_id, date_from=None, date_to=None):
        """Open sale orders containing a specific product (called from JS product row click)."""
        self.ensure_one()
        partners = self._get_all_partners()
        domain = [
            ("order_id.partner_id", "in", partners.ids),
            ("order_id.state", "=", "sale"),
            ("product_id.product_tmpl_id", "=", product_tmpl_id),
        ]
        if date_from:
            domain.append(("order_id.date_order", ">=", date_from))
        if date_to:
            domain.append(("order_id.date_order", "<=", date_to))
        order_lines = self.env["sale.order.line"].search(domain)
        order_ids = order_lines.mapped("order_id").ids
        product_tmpl = self.env["product.template"].browse(product_tmpl_id)
        return {
            "type": "ir.actions.act_window",
            "name": _("Orders for %s") % product_tmpl.name,
            "res_model": "sale.order",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("id", "in", order_ids)],
            "context": {"default_partner_id": self.owner_id.id if self.owner_id else False},
        }

    def action_print_annual_review(self):
        """Print the annual review report."""
        self.ensure_one()
        return self.env.ref("crm_account_management.action_report_annual_review").report_action(
            self
        )
