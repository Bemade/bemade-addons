# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from dateutil.relativedelta import relativedelta

from odoo import fields, models
from odoo.tools.float_utils import float_compare, float_is_zero

from ..tools.cost_source import CostResolution, CostSource


class ProductProduct(models.Model):
    _inherit = "product.product"

    # -- extension point ---------------------------------------------------

    def _cost_sources(self, qty, date, currency, company, qty_from_stock=0.0):
        """Return the cost sources covering ``qty``, best-first.

        This is the extension point. A module that knows another way to
        establish a cost overrides this, calls super(), and appends its own
        sources; resolution, confidence and evidence then apply to them
        unchanged.

        ``qty_from_stock`` is supplied by the caller rather than discovered
        here. This module does not know what a demand is -- a sale line, a
        manufacturing order and a forecast each reason about availability
        differently, and each is entitled to its own answer.
        """
        self.ensure_one()
        rounding = self.uom_id.rounding
        sources = []

        covered = max(0.0, min(qty_from_stock, qty))
        if not float_is_zero(covered, precision_rounding=rounding):
            sources.append(
                CostSource(
                    key="stock",
                    qty=covered,
                    unit_price=self._cost_source_convert(
                        self.standard_price, company.currency_id, currency, company, date
                    ),
                    # Stock was bought at a price we actually paid, so its age
                    # is not in question: we own the goods at that cost.
                    priced_on=date,
                    in_force=True,
                )
            )

        remaining = qty - covered
        if float_compare(remaining, 0.0, precision_rounding=rounding) > 0:
            vendor = self._cost_source_vendor(remaining, date, currency, company)
            if vendor:
                sources.append(vendor)
        return sources

    # -- built-in sources --------------------------------------------------

    def _cost_source_vendor(self, qty, date, currency, company):
        """The best available evidence of what a vendor would charge for ``qty``.

        Candidates come from :meth:`_cost_source_price_candidates`, which is the
        second extension point: modules contribute other ways of knowing a
        price, and the best-evidenced one wins. They compete rather than
        accumulate, because they are all answering the same question.
        """
        self.ensure_one()
        candidates = self._cost_source_price_candidates(qty, date, currency, company)
        if not candidates:
            return None
        return sorted(candidates, key=self._cost_source_rank)[0]

    def _cost_source_rank(self, source):
        """Ordering over price evidence, best first.

        An agreement in force outranks loose evidence, because it is a promise
        rather than an observation. Below that, the most recently established
        price wins, whoever contributed it -- a plugin cannot jump the queue
        merely by being a plugin. Undated evidence sorts last: it may well be
        current, but nothing on file says so.
        """
        return (
            0 if source.in_force else 1,
            0 if source.priced_on else 1,
            -source.priced_on.toordinal() if source.priced_on else 0,
        )

    def _cost_source_price_candidates(self, qty, date, currency, company):
        """Return every known indication of a vendor price for ``qty``.

        Extension point. Override, call super(), and append your own evidence;
        ranking, confidence and evidence-reporting then apply to it unchanged.
        """
        self.ensure_one()
        candidates = []
        seller = self._select_seller(quantity=qty, date=date, uom_id=self.uom_id)
        if seller:
            candidates.append(self._cost_source_from_seller(seller, qty, currency, company, date, in_force=bool(seller.date_start or seller.date_end)))
        fallback = self._cost_source_last_known_seller(qty)
        if fallback and fallback != seller:
            candidates.append(self._cost_source_from_seller(fallback, qty, currency, company, date, in_force=False))
        return candidates

    def _cost_source_last_known_seller(self, qty):
        """The most recent supplier price on file, whether or not it still applies.

        Used when Odoo's own seller lookup finds nothing, which happens when
        every agreement has lapsed. The price is still the last thing we knew;
        it is reported as evidence rather than as a commitment.
        """
        self.ensure_one()
        candidates = self.seller_ids.filtered(
            lambda s: not s.min_qty or s.min_qty <= qty
        )
        if not candidates:
            return self.env["product.supplierinfo"]
        dated = candidates.filtered("date_start")
        if dated:
            return max(dated, key=lambda s: s.date_start)
        return candidates.sorted("sequence")[0]

    def _cost_source_from_seller(self, seller, qty, currency, company, date, in_force):
        return CostSource(
            key="vendor",
            qty=qty,
            unit_price=self._cost_source_convert(
                seller.price, seller.currency_id, currency, company, date
            ),
            # date_start is when this price was agreed. write_date is when the
            # row was last touched, which on an imported catalogue is the date
            # of the import -- it says nothing about the price, so it is never
            # consulted. No date means unknown, and unknown is never fresh.
            priced_on=seller.date_start or None,
            in_force_until=seller.date_end or None,
            in_force=in_force,
        )

    def _cost_source_convert(self, amount, from_currency, to_currency, company, date):
        if not from_currency or not to_currency or from_currency == to_currency:
            return amount
        return from_currency._convert(
            from_amount=amount,
            to_currency=to_currency,
            company=company,
            date=date,
            round=False,
        )

    # -- resolution --------------------------------------------------------

    def _resolve_cost(
        self,
        qty=1.0,
        date=None,
        currency=None,
        company=None,
        qty_from_stock=0.0,
        delivery_date=None,
    ):
        """Resolve a unit cost for ``qty`` and report the evidence behind it."""
        self.ensure_one()
        company = company or self.env.company
        currency = currency or company.currency_id
        date = date or fields.Date.context_today(self)

        sources = self._cost_sources(qty, date, currency, company, qty_from_stock)
        resolution = CostResolution(sources=sources)
        if not sources:
            resolution.evidence.append(
                self.env._(
                    "No price is known for this product: it has no vendor price "
                    "and no stock on hand."
                )
            )
            return resolution

        covered = sum(source.qty for source in sources)
        resolution.unit_cost = (
            sum(source.subtotal for source in sources) / covered if covered else 0.0
        )
        resolution.confidence = self._cost_source_confidence(sources, date)
        resolution.evidence = self._cost_source_evidence(sources, date, qty)
        resolution.warnings = self._cost_source_warnings(sources, delivery_date)
        return resolution

    def _cost_source_confidence(self, sources, date):
        """Firm only when every contributing source is firm.

        A blend is no better than its weakest half: quoting a firm price for
        part of a line and a guess for the rest is still quoting a guess.
        """
        if not sources:
            return "unknown"
        cutoff = date - relativedelta(months=self.env["res.config.settings"]._price_age_months())
        for source in sources:
            if source.in_force:
                continue
            if source.priced_on is None or source.priced_on < cutoff:
                return "estimated"
        return "firm"

    def _cost_source_evidence(self, sources, date, qty):
        months = self.env["res.config.settings"]._price_age_months()
        blended = len(sources) > 1
        evidence = []
        for source in sources:
            share = ""
            if blended:
                share = self.env._(
                    " Covers %(qty)s of %(total)s.",
                    qty=self._cost_source_format_qty(source.qty),
                    total=self._cost_source_format_qty(qty),
                )
            if source.key == "stock":
                evidence.append(
                    self.env._(
                        "Pricing based on current stock availability and stock "
                        "valuation."
                    )
                    + share
                )
            elif source.in_force and source.in_force_until:
                evidence.append(
                    self.env._(
                        "Pricing is firm based on a date-bounded vendor pricelist, "
                        "valid until %(until)s.",
                        until=fields.Date.to_string(source.in_force_until),
                    )
                    + share
                )
            elif source.in_force:
                evidence.append(
                    self.env._(
                        "Pricing is firm based on an open-ended vendor agreement, "
                        "in force since %(since)s.",
                        since=fields.Date.to_string(source.priced_on),
                    )
                    + share
                )
            elif source.priced_on is None:
                evidence.append(
                    self.env._(
                        "Supplier price is on file but undated, so its age cannot "
                        "be established. Treat it as an estimate until confirmed."
                    )
                    + share
                )
            else:
                evidence.append(
                    self.env._(
                        "Supplier price is more than %(months)s months old. No "
                        "transaction since %(since)s.",
                        months=months,
                        since=fields.Date.to_string(source.priced_on),
                    )
                    + share
                    if source.priced_on < date - relativedelta(months=months)
                    else self.env._(
                        "Supplier price was last set on %(since)s, within the last "
                        "%(months)s months.",
                        since=fields.Date.to_string(source.priced_on),
                        months=months,
                    )
                    + share
                )
        return evidence

    def _cost_source_warnings(self, sources, delivery_date):
        """Flag a price that is firm today but will not be by delivery.

        The case a plain age check cannot see: nothing is stale, and the quote
        is still wrong.
        """
        if not delivery_date:
            return []
        warnings = []
        for source in sources:
            if source.in_force_until and source.in_force_until < delivery_date:
                warnings.append(
                    self.env._(
                        "The vendor agreement backing this price expires on "
                        "%(expiry)s, before the delivery date of %(delivery)s.",
                        expiry=fields.Date.to_string(source.in_force_until),
                        delivery=fields.Date.to_string(delivery_date),
                    )
                )
        return warnings

    def _cost_source_format_qty(self, qty):
        return ("%.2f" % qty).rstrip("0").rstrip(".")
