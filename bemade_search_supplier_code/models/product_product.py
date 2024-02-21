from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    supplier_codes = fields.Char(
        compute='_compute_supplier_codes',
        string='Supplier Codes',
        store=True,
        search='_search_supplier_codes')

    @api.depends('variant_seller_ids', 'variant_seller_ids.product_code')
    def _compute_supplier_codes(self):
        for product in self:
            codes = filter(lambda x: isinstance(x, str), product.variant_seller_ids.mapped('product_code'))
            product.supplier_codes = ', '.join(codes)

    def _search_supplier_codes(self, operator, value):
        if not value:
            return []

        supplierinfo_ids = self.env['product.supplierinfo'].search([('product_code', operator, value)])
        product_ids = supplierinfo_ids.mapped('product_id.id')

        return [('id', 'in', product_ids)]