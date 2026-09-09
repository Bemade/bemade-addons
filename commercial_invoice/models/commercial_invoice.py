from collections import Counter, OrderedDict

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError


class CommercialInvoice(models.Model):
    _name = "commercial.invoice"
    _description = "Commercial Invoice for Export"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Reference", required=True, copy=False, readonly=True, default="New"
    )
    date = fields.Date(
        string="Export Date", required=True, default=fields.Date.context_today
    )
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Done"), ("cancelled", "Cancelled")],
        string="Status",
        default="draft",
        tracking=True,
    )
    line_source = fields.Selection(
        [("invoice", "Invoices"), ("picking", "Deliveries")],
        string="Line Source",
        required=True,
        default="invoice",
        tracking=True,
        help="Whether this commercial invoice sources its content from linked "
        "Invoices or from explicitly selected Deliveries. With 'Deliveries' the "
        "content comes solely from the Deliveries field (picking_ids).",
    )

    # Related parties
    partner_id = fields.Many2one("res.partner", string="Consignee", required=True)
    importer_id = fields.Many2one("res.partner", string="Importer of Record")
    customs_broker_id = fields.Many2one("res.partner", string="Customs Broker")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.ref("base.USD")
    )
    related_parties = fields.Boolean(string="Related Parties", default=False)

    # Invoice lines and related fields
    invoice_ids = fields.Many2many(
        "account.move",
        string="Invoices",
        domain=[("move_type", "in", ["out_invoice", "in_refund"])],
    )
    payment_term_id = fields.Many2one("account.payment.term", string="Payment Terms")
    incoterm_id = fields.Many2one("account.incoterms", string="Incoterms")

    # Delivery (stock.picking) source — explicit picking selection.
    #
    # NOTE (field-ownership intent, task 3705 MR-1): picking_ids is REUSING the
    # exact relation/column names that ``verajet_commercial_invoice`` already
    # uses for its own ``picking_ids`` M2M
    # (rel ``commercial_invoice_picking_rel``, columns
    # ``commercial_invoice_id`` / ``picking_id``).  This is deliberate so that
    # a later move of field ownership from the Vera overlay down into this base
    # module is a no-op at the database level (same table/columns) rather than
    # a delete+recreate.  Verajet's own ``picking_ids`` declaration is removed
    # in the downstream MR-2; until then both declare the same relation, which
    # the ORM collapses onto one table.
    picking_ids = fields.Many2many(
        "stock.picking",
        "commercial_invoice_picking_rel",
        "commercial_invoice_id",
        "picking_id",
        string="Deliveries",
        domain="[('picking_type_id.code', '=', 'outgoing')]",
    )
    po_numbers = fields.Char(
        string="PO Numbers",
        compute="_compute_delivery_header",
        compute_sudo=True,
        store=True,
        readonly=False,
    )
    carrier_id = fields.Many2one(
        "delivery.carrier",
        string="Carrier",
        compute="_compute_delivery_header",
        compute_sudo=True,
        store=True,
        readonly=False,
    )
    ship_date = fields.Date(
        string="Ship Date",
        compute="_compute_delivery_header",
        compute_sudo=True,
        store=True,
        readonly=False,
    )

    # Shipping details
    number_of_packages = fields.Integer(string="Number of Packages")
    total_weight = fields.Float(string="Total Weight (kg)")
    packaging_cost = fields.Monetary(
        string="Packaging Cost", currency_field="currency_id"
    )
    freight_cost = fields.Monetary(string="Freight Cost", currency_field="currency_id")
    insurance_cost = fields.Monetary(
        string="Insurance Cost", currency_field="currency_id"
    )
    other_cost = fields.Monetary(string="Other Costs", currency_field="currency_id")

    # Computed fields
    invoice_amount = fields.Monetary(
        string="Invoice Amount",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )
    total_amount = fields.Monetary(
        string="Total Amount",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("commercial.invoice") or "New"
                )
        return super().create(vals_list)

    def _get_report_lines(self):
        """Return a uniform list of dicts for QWeb report line iteration.

        Each dict has the shape::

            {
                'name': str,
                'default_code': str,
                'hs_code': str,
                'quantity': float,
                'uom': res.uom record or False,
                'price_unit': float,
                'price_subtotal': float,
                'country_of_origin': str,
            }

        When ``line_source == 'invoice'`` the data comes from
        ``account.move.line`` records linked through ``invoice_ids``.

        When ``line_source == 'picking'`` the data comes from the
        ``stock.move`` records of the explicitly selected ``picking_ids``.
        Moves are aggregated by (product_id, price_unit) so different unit
        prices for the same product produce separate rows.  ``picking_ids`` is
        the *single source of truth*: with no deliveries selected the picking
        path yields no lines (task 3705 refinement — no partner-search
        fallback; see :meth:`action_select_partner_deliveries`).
        """
        self.ensure_one()
        if self.line_source == "picking":
            return self._get_report_lines_from_pickings()
        return self._get_report_lines_from_invoices()

    def _get_report_lines_from_invoices(self):
        """Build report lines from linked account.move.line records."""
        lines = []
        for line in self.invoice_ids.mapped("invoice_line_ids").filtered("product_id"):
            lines.append(
                {
                    "name": line.product_id.name,
                    "default_code": line.product_id.default_code or "",
                    "hs_code": line.product_id.hs_code or "",
                    "quantity": line.quantity,
                    "uom": line.product_uom_id,
                    "price_unit": line.price_unit,
                    "price_subtotal": line.price_subtotal,
                    "country_of_origin": line.product_id.country_of_origin.name or "",
                }
            )
        return lines

    def _partner_outgoing_pickings_domain(self):
        """Domain for the CI partner's done outgoing deliveries.

        Used by :meth:`action_select_partner_deliveries` to PRE-FILL
        ``picking_ids`` (a convenience sweep the user can then trim).  It is
        NOT a content/sourcing path — report lines come only from the explicit
        ``picking_ids`` selection (task 3705 refinement).
        """
        self.ensure_one()
        commercial_partner = self.partner_id.commercial_partner_id
        return [
            ("partner_id.commercial_partner_id", "=", commercial_partner.id),
            ("picking_type_id.code", "=", "outgoing"),
            ("state", "=", "done"),
        ]

    def _get_report_lines_from_pickings(self):
        """Build report lines from the explicitly selected ``picking_ids``.

        ``picking_ids`` is the single source of truth: with no deliveries
        selected this yields no lines (no partner-search fallback — task 3705
        refinement).  Selected pickings may not yet be validated (the CI can be
        built before the delivery is done), so the move ``state == 'done'``
        filter is intentionally not applied; cancelled moves are excluded.
        Moves are aggregated by (product_id, price_unit).
        """
        pickings = self.picking_ids
        if not pickings:
            return []
        moves = pickings.mapped("move_ids").filtered(
            lambda m: m.product_id and m.state != "cancel"
        )

        # Aggregate by (product_id, price_unit derived from sale_line_id)
        aggregated = {}
        for move in moves:
            price_unit = (
                move.sale_line_id.price_unit if move.sale_line_id else 0.0
            )
            key = (move.product_id.id, price_unit)
            if key not in aggregated:
                aggregated[key] = {
                    "product": move.product_id,
                    "price_unit": price_unit,
                    "quantity": 0.0,
                    "uom": move.product_uom,
                }
            # Selected pickings may not yet be validated, so use the demanded
            # quantity, which is set before validation.
            aggregated[key]["quantity"] += move.product_uom_qty

        lines = []
        for (product_id, price_unit), data in aggregated.items():
            product = data["product"]
            qty = data["quantity"]
            lines.append(
                {
                    "name": product.name,
                    "default_code": product.default_code or "",
                    "hs_code": product.hs_code or "",
                    "quantity": qty,
                    "uom": data["uom"],
                    "price_unit": price_unit,
                    "price_subtotal": qty * price_unit,
                    "country_of_origin": product.country_of_origin.name or "",
                }
            )
        return lines

    @api.depends(
        "invoice_ids",
        "invoice_ids.amount_total",
        "line_source",
        "partner_id",
        "picking_ids",
        "packaging_cost",
        "freight_cost",
        "insurance_cost",
        "other_cost",
    )
    def _compute_amounts(self):
        for record in self:
            if record.line_source == "picking":
                record.invoice_amount = sum(
                    row["price_subtotal"] for row in record._get_report_lines()
                )
            else:
                record.invoice_amount = sum(record.invoice_ids.mapped("amount_total"))
            record.total_amount = (
                record.invoice_amount
                + record.packaging_cost
                + record.freight_cost
                + record.insurance_cost
                + record.other_cost
            )

    @api.depends(
        "picking_ids",
        "picking_ids.sale_id",
        "picking_ids.sale_id.client_order_ref",
        "picking_ids.carrier_id",
        "picking_ids.scheduled_date",
        "picking_ids.date_done",
    )
    def _compute_delivery_header(self):
        """Aggregate header fields from the selected deliveries.

        Ported from ``verajet_commercial_invoice`` (task 3705 MR-1): PO
        numbers, carrier and ship date are derived from ``picking_ids`` so a
        delivery-sourced commercial invoice carries the shipment header that a
        customs document needs.
        """
        for record in self:
            pickings = record.picking_ids
            # PO numbers: unique, keep insertion order, prefer client_order_ref,
            # fall back to SO name when ref missing, then picking origin.
            refs = OrderedDict()
            for pick in pickings:
                so = pick.sale_id
                ref = (so.client_order_ref or so.name) if so else pick.origin
                if ref:
                    refs[ref] = True
            record.po_numbers = ", ".join(refs.keys()) if refs else False

            # Carrier: most common across pickings; ties broken by first seen.
            carriers = [p.carrier_id for p in pickings if p.carrier_id]
            if carriers:
                counter = Counter(c.id for c in carriers)
                most_common_id, _count = counter.most_common(1)[0]
                record.carrier_id = most_common_id
            else:
                record.carrier_id = False

            # Ship date: earliest of date_done (if validated) else scheduled_date.
            candidates = []
            for pick in pickings:
                dt = pick.date_done or pick.scheduled_date
                if dt:
                    candidates.append(dt)
            record.ship_date = min(candidates).date() if candidates else False

    def action_recompute_amounts(self):
        """Manually trigger amount recomputation.

        When ``line_source='picking'`` the ORM cannot automatically detect
        changes to ``stock.move.quantity`` (no persisted relation exists).
        Users must click this button to refresh totals after delivery changes.
        """
        self._compute_amounts()

    def action_select_partner_deliveries(self):
        """Pre-fill ``picking_ids`` with the partner's done outgoing deliveries.

        A one-click convenience: it sweeps every done outgoing ``stock.picking``
        for this CI's commercial partner and writes them into ``picking_ids``,
        which the user can then trim.  This only POPULATES the field — it does
        NOT itself source or store report content (content comes solely from
        ``picking_ids``).  Replaces the old partner-search *sourcing* fallback
        (task 3705 refinement): choosing a partner no longer silently pulls
        every historical delivery onto the document; the user opts in and edits.
        """
        for record in self:
            if not record.partner_id:
                raise UserError(
                    _("Select a consignee before pre-filling deliveries.")
                )
            pickings = self.env["stock.picking"].search(
                record._partner_outgoing_pickings_domain()
            )
            record.picking_ids = [Command.set(pickings.ids)]
        return True

    def action_confirm(self):
        for record in self:
            if not record.invoice_ids and not record.picking_ids:
                raise UserError(
                    _(
                        "A commercial invoice must have at least one invoice "
                        "or one delivery linked."
                    )
                )
        self.write({"state": "done"})

    def action_draft(self):
        self.write({"state": "draft"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.payment_term_id = self.partner_id.property_payment_term_id

    @api.model
    def _prepare_commercial_invoice_from_invoices(self, invoices):
        """Prepare commercial invoice values from a set of invoices."""
        if not invoices:
            raise UserError(_("No invoices selected."))

        # Get unique values for key fields
        currencies = invoices.mapped("currency_id")
        payment_terms = invoices.mapped("invoice_payment_term_id")
        incoterms = invoices.mapped("invoice_incoterm_id")
        companies = invoices.mapped("company_id")

        # Validate consistency
        if len(currencies) > 1:
            raise UserError(_("Selected invoices have different currencies."))
        if len(companies) > 1:
            raise UserError(_("Selected invoices are from different companies."))

        # Get shipping and billing partners
        shipping_partners = invoices.mapped("partner_shipping_id.commercial_partner_id")
        billing_partners = invoices.mapped("partner_id.commercial_partner_id")

        # Prepare values
        vals = {
            "invoice_ids": [(6, 0, invoices.ids)],
            "company_id": companies[0].id,
            "currency_id": currencies[0].id,
            "partner_id": (
                shipping_partners[0].id if len(shipping_partners) == 1 else False
            ),
            "importer_id": (
                billing_partners[0].id if len(billing_partners) == 1 else False
            ),
            "payment_term_id": (
                payment_terms[0].id if len(payment_terms) == 1 else False
            ),
            "incoterm_id": incoterms[0].id if len(incoterms) == 1 else False,
        }

        return vals

    @api.model
    def create_from_invoices(self, invoices):
        """Create a commercial invoice from a set of invoices."""
        vals = self._prepare_commercial_invoice_from_invoices(invoices)
        return self.create(vals)

    @api.model
    def _prepare_commercial_invoice_from_pickings(self, pickings):
        """Prepare commercial invoice values from a set of deliveries.

        Ported from ``verajet_commercial_invoice`` (task 3705 MR-1).  Sets
        ``line_source='picking'`` so the report/totals use the delivery path,
        and stores the explicit ``picking_ids`` so the selection-first
        aggregation applies.
        """
        if not pickings:
            raise UserError(_("No deliveries selected."))

        companies = pickings.mapped("company_id")
        if len(companies) > 1:
            raise UserError(_("Selected deliveries are from different companies."))

        # Shipping = partner on picking (consignee); importer = commercial partner.
        shipping_partners = pickings.mapped("partner_id.commercial_partner_id")
        consignee = shipping_partners[0] if len(shipping_partners) == 1 else False

        # Align currency with the SO; fall back to USD (cross-border default).
        sale_orders = pickings.mapped("sale_id")
        currency = False
        if sale_orders:
            currencies = sale_orders.mapped("currency_id")
            if len(currencies) == 1:
                currency = currencies[0].id
        if not currency:
            currency = self.env.ref("base.USD").id

        incoterms = sale_orders.mapped("incoterm")
        payment_terms = sale_orders.mapped("payment_term_id")

        vals = {
            "line_source": "picking",
            "picking_ids": [Command.set(pickings.ids)],
            "company_id": companies[:1].id,
            "currency_id": currency,
            "partner_id": consignee.id if consignee else False,
            "importer_id": consignee.id if consignee else False,
            "incoterm_id": incoterms[0].id if len(incoterms) == 1 else False,
            "payment_term_id": (
                payment_terms[0].id if len(payment_terms) == 1 else False
            ),
        }
        return vals

    @api.model
    def create_from_pickings(self, pickings):
        """Create a commercial invoice from a set of deliveries."""
        vals = self._prepare_commercial_invoice_from_pickings(pickings)
        return self.create(vals)
