# -*- coding: utf-8 -*-

from odoo import models, fields, api
from markupsafe import Markup


class ProductSupplierInfo(models.Model):
    _name = "product.supplierinfo"
    _inherit = ["product.supplierinfo", "mail.thread", "mail.activity.mixin"]

    # Commented out because breaking basic Odoo tests. See if this is really needed.

    # _sql_constraints = [("supplierinfo_product_tmpl_id_no_null",
    #                      "CHECK((product_tmpl_id IS NOT NULL))",
    #                      "Supplier pricelist need product template"),
    #                     ]

    # We add tracking to the fields that are displayed in the chatter
    partner_id = fields.Many2one(tracking=True, domain=[("is_company", "=", True)])

    partner_id = fields.Many2one(tracking=True)
    product_name = fields.Char(tracking=True)
    product_code = fields.Char(tracking=True)
    product_uom = fields.Many2one(tracking=True)
    min_qty = fields.Float(tracking=True)
    currency_id = fields.Many2one(tracking=True)
    date_start = fields.Date(tracking=True)
    date_end = fields.Date(tracking=True)
    product_id = fields.Many2one(tracking=True)
    product_tmpl_id = fields.Many2one(tracking=True)
    delay = fields.Integer(tracking=True)
    price = fields.Float(tracking=True)
    discount = fields.Float(tracking=True)
    delay = fields.Integer(tracking=True)

    def _generate_chatter(self, vals, operation):
        if len(self) == 1 and self.product_tmpl_id:
            name = self.product_id.name or self.product_tmpl_id.name
            msg = ""
            headmsg = (
                f"<a href='#' data-oe-model='product.supplierinfo' data-oe-id='{self.id}'>"
                f"Price {operation} for {name} : <br /></a>"
            )
            if self.min_qty > 0:
                msg += f"<li>Minimum qty : {self.min_qty}</li>"
            if self.date_start:
                msg += f"<li>Starting : {self.date_start}</li>"
            if self.date_end:
                msg += f"<li>Ending : {self.date_end}</li>"
            if msg:
                msg = headmsg + "<ul>" + msg + "</ul>"
            else:
                msg = headmsg
            for change in vals:
                msg += f"{change} --> {vals[change]}<br />"
            # Should always be there
            if self.product_tmpl_id:
                self.product_tmpl_id.message_post(
                    body=Markup(msg),
                )
            # only for variant
            if self.product_id:
                self.product_id.message_post(body=Markup(msg))

    def write(self, vals):
        res = super(ProductSupplierInfo, self).write(vals)
        self._generate_chatter(vals, "modified")
        return res

    def supplierinfo_show_details(self):
        """
        Action to open product.supplierinfo (pricelist) in its own windows and not in a javascript
        popup to avoid loosing product_tmpl_id.  We rely on both context and domain to pass the
        information
        """
        return {
            "name": "Supplier price",
            "view_type": "form",
            "view_mode": "form",
            "res_id": self.id,
            "context": self.env.context,
            "res_model": "product.supplierinfo",
            "domain": [
                ("product_tmpl_id", "=", self.product_tmpl_id.id),
                ("product_id", "=", self.product_id.id if self.product_id else False),
            ],
            "type": "ir.actions.act_window",
        }
