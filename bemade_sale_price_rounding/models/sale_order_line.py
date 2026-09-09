# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.tools import float_round


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    price_unit = fields.Float(digits="Product Price")
    purchase_price = fields.Float(digits="Product Price")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _round_to_price_precision(self, value, currency=None):
        """Round *value* to the order currency's precision, or to the
        ``Product Price`` decimal precision when no currency is available.

        :param float value: the value to round.
        :param res.currency currency: optional currency record.
        :return float: rounded value.
        """
        if currency:
            return currency.round(value)
        dp = self.env["decimal.precision"].precision_get("Product Price")
        return float_round(value, precision_digits=dp)

    # ------------------------------------------------------------------
    # Bug 1 — round price_unit in cache before _compute_amount runs
    # ------------------------------------------------------------------

    def _reset_price_unit(self):
        """Override: after super sets price_unit from pricelist computation,
        round price_unit and technical_price_unit in cache so that
        _compute_amount reads the rounded value.
        """
        super()._reset_price_unit()
        currency = (
            self.currency_id
            or self.order_id.currency_id
            or self.company_id.currency_id
            or self.env.company.currency_id
        )
        rounded = self._round_to_price_precision(self.price_unit, currency)
        if rounded != self.price_unit:
            self.update({
                "price_unit": rounded,
                "technical_price_unit": rounded,
            })

    # ------------------------------------------------------------------
    # Bug 2 — round purchase_price in cache after every compute
    # ------------------------------------------------------------------

    def _compute_purchase_price(self):
        """Override: after the full super() chain writes purchase_price,
        round the in-cache value to Product Price precision so that PDF
        templates and downstream consumers never see raw unrounded floats.
        """
        super()._compute_purchase_price()
        for line in self:
            if not line.purchase_price:
                continue
            currency = (
                line.currency_id
                or line.order_id.currency_id
                or line.company_id.currency_id
                or line.env.company.currency_id
            )
            rounded = line._round_to_price_precision(line.purchase_price, currency)
            if rounded != line.purchase_price:
                line.purchase_price = rounded

    # ------------------------------------------------------------------
    # Round at direct write / create (covers imports, API writes, etc.)
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        dp = self.env["decimal.precision"].precision_get("Product Price")
        for vals in vals_list:
            for fname in ("price_unit", "technical_price_unit", "purchase_price"):
                if fname in vals and vals[fname] is not None:
                    vals[fname] = float_round(vals[fname], precision_digits=dp)
        return super().create(vals_list)

    def write(self, vals):
        dp = self.env["decimal.precision"].precision_get("Product Price")
        for fname in ("price_unit", "technical_price_unit", "purchase_price"):
            if fname in vals and vals[fname] is not None:
                vals[fname] = float_round(vals[fname], precision_digits=dp)
        return super().write(vals)
