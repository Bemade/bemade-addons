# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from datetime import datetime

from odoo import fields, models, tools


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _get_bom_cost_pricelist_price(
        self, rule, date=None, quantity=None, product_id=None
    ):
        """Get the price from the product's BOM cost rollup.

        Structurally parallel to
        ``product_pricelist_supplierinfo``'s
        ``_get_supplierinfo_pricelist_price``: it resolves a raw cost (here the
        BOM cost rollup via ``mrp_account``'s ``_compute_bom_price`` instead of
        the supplier price), then applies the pricelist rule's formula chain
        (discount, rounding, surcharge, min/max margin) and UoM conversion.
        """
        self.ensure_one()
        price = 0.0
        product = self.product_variant_id
        if product_id:
            product = product.browse(product_id)
        if isinstance(date, datetime):
            date = date.date()
        # The product_variant_id returns empty recordset if template is not
        # active, so we must ensure a variant exists before resolving the BOM.
        if product:
            bom = self.env["mrp.bom"]._bom_find(
                product, company_id=rule.company_id.id
            )[product]
            if bom:
                # Non-mutating cost rollup (does NOT touch standard_price).
                price = product._compute_bom_price(bom)
        if price:
            # Convert the BOM cost (expressed in the product's company currency)
            # to the pricelist currency when they differ.
            cost_currency = (
                rule.company_id.currency_id
                or self.env.company.currency_id
            )
            if rule.currency_id != cost_currency:
                convert_date = date or self.env.context.get(
                    "date", fields.Date.today()
                )
                price = cost_currency._convert(
                    price,
                    rule.currency_id,
                    rule.company_id or self.env.company,
                    convert_date,
                )

            # Apply the pricelist rule's formula chain. This replicates the
            # relevant part of product.pricelist._compute_price_rule, mirroring
            # product_pricelist_supplierinfo (pricelist methods are atomic, so
            # we cannot defer to super for this).
            qty_uom_id = self._context.get("uom") or self.uom_id.id
            price_uom = self.env["uom.uom"].browse([qty_uom_id])
            price_limit = price
            price = (price - (price * (rule.price_discount / 100))) or 0.0
            if rule.price_round:
                price = tools.float_round(price, precision_rounding=rule.price_round)
            if rule.price_surcharge:
                price_surcharge = self.uom_id._compute_price(
                    rule.price_surcharge, price_uom
                )
                price += price_surcharge
            if rule.price_min_margin:
                price_min_margin = self.uom_id._compute_price(
                    rule.price_min_margin, price_uom
                )
                price = max(price, price_limit + price_min_margin)
            if rule.price_max_margin:
                price_max_margin = self.uom_id._compute_price(
                    rule.price_max_margin, price_uom
                )
                price = min(price, price_limit + price_max_margin)
        return price

    def _price_compute(
        self, price_type, uom=None, currency=None, company=False, date=False
    ):
        """Return a dummy not-falsy price for the BOM-cost base, so the native
        ``_compute_base_price`` does not raise on the unknown ``bom_cost``
        price_type. The real value is filled in afterwards by
        ``product.pricelist.item._compute_price``. Mirrors
        ``product_pricelist_supplierinfo``.
        """
        if price_type == "bom_cost":
            return dict.fromkeys(self.ids, 1.0)
        return super()._price_compute(
            price_type, uom=uom, currency=currency, company=company, date=date
        )
