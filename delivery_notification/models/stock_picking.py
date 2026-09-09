import base64
import logging
from odoo import models, _
from typing import Any, cast

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super().button_validate()
        for picking in self:
            if picking.state == "done" and picking.carrier_tracking_ref:
                picking._notify_tracking_number()
        return res

    def _notify_tracking_number(self):
        """Send an email notification when tracking number is set.

        Recipients depend on company setting:
        - 'followers': All followers of the sale order (Odoo default behavior)
        - 'order_contact': Only the contact who placed the order
        """
        self.ensure_one()

        # Only process outgoing pickings with tracking numbers and linked to a sale order
        if (
            self.picking_type_code != "outgoing"
            or not self.carrier_tracking_ref
            or not self.sale_id
        ):
            return

        # Get the mail template
        template = self.env.ref(
            "delivery_notification.mail_template_tracking_notification",
            raise_if_not_found=False,
        )
        if not template:
            _logger.error(
                "Mail template 'mail_template_tracking_notification' not found"
            )
            return

        # Build tracking URL if available
        tracking_url = None
        if self.carrier_id:
            try:
                # Try to get tracking URL using the carrier's method
                if hasattr(self.carrier_id, "get_tracking_link"):
                    tracking_url = self.carrier_id.get_tracking_link(self)
            except Exception as e:
                _logger.warning(
                    "Failed to get tracking link for picking %s: %s", self.name, str(e)
                )

        # Render the message body
        body = template._render_field(
            "body_html",
            self.sale_id.ids,
            compute_lang=True,
            add_context={
                "tracking_ref": self.carrier_tracking_ref,
                "tracking_url": tracking_url,
            },
        )[self.sale_id.id]

        # Generate delivery order PDF attachment
        attachments = []
        try:
            report = self.env.ref(
                "stock.action_report_delivery", raise_if_not_found=False
            )
            if report:
                pdf_content, __ = cast(
                    Any, report._render(report_ref=report, res_ids=self.ids)
                )
                attachment = self.env["ir.attachment"].create(
                    {
                        "name": f"Delivery_Order_{self.name}.pdf",
                        "type": "binary",
                        "datas": base64.b64encode(pdf_content),
                        "res_model": "stock.picking",
                        "res_id": self.id,
                        "mimetype": "application/pdf",
                    }
                )
                attachments.append(attachment.id)
        except Exception as e:
            _logger.warning(
                "Failed to generate delivery PDF for picking %s: %s",
                self.name,
                str(e),
            )

        # Determine recipients based on company setting
        company = self.sale_id.company_id or self.env.company
        recipient_mode = company.delivery_notification_recipient

        # Post message to the sale order
        message_kwargs = {
            "body": body,
            "subject": template.subject or _("Shipment Tracking Information"),
            "message_type": "notification",
        }
        if attachments:
            message_kwargs["attachment_ids"] = attachments

        if recipient_mode == "order_contact":
            # Send only to the contact that placed the order.
            # Omit subtype so only explicit partner_ids are notified.
            recipient_partner = self.sale_id.partner_id
            if not recipient_partner.email:
                _logger.warning(
                    "Order contact %s has no email, skipping delivery "
                    "notification for sale order %s",
                    recipient_partner.display_name,
                    self.sale_id.name,
                )
                return
            message_kwargs["partner_ids"] = [recipient_partner.id]
        else:
            # Notify all followers via comment subtype
            message_kwargs["message_type"] = "comment"
            message_kwargs["subtype_xmlid"] = "mail.mt_comment"

        self.sale_id.message_post(**message_kwargs)
