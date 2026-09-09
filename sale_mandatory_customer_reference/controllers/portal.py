from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.sale.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class CustomerPortalInherit(CustomerPortal):

    def _prepare_quotations_domain(self, partner):
        domain = super()._prepare_quotations_domain(partner)
        return domain

    def _prepare_sale_portal_rendering_values(
        self,
        page=1,
        date_begin=None,
        date_end=None,
        sortby=None,
        quotation_page=False,
        **kwargs
    ):
        values = super()._prepare_sale_portal_rendering_values(
            page=page,
            date_begin=date_begin,
            date_end=date_end,
            sortby=sortby,
            quotation_page=quotation_page,
            **kwargs,
        )
        values["enforce_customer_reference"] = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "sale_mandatory_customer_reference.enforce_customer_reference", False
            )
        )
        return values

    @http.route(
        ["/my/orders/<int:order_id>/update_reference"],
        type="json",
        auth="public",
        website=True,
    )
    def portal_update_sale_reference(
        self, order_id, reference, access_token=None, **kw
    ):
        try:
            order_sudo = self._document_check_access(
                "sale.order", order_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return {"error": _("Access Denied")}

        if order_sudo.state not in ("draft", "sent"):
            return {"error": _("Order cannot be modified in its current state")}

        order_sudo.write({"client_order_ref": reference})
        return {"success": True}
