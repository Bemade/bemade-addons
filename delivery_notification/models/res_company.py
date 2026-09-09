from odoo import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    delivery_notification_recipient = fields.Selection(
        [
            ("followers", "All followers of the sale order"),
            ("order_contact", "Order contact only"),
        ],
        string="Delivery Notification Recipients",
        default="order_contact",
        help=(
            "Determines who receives the delivery tracking notification:\n"
            "- All followers: All followers of the sale order (Odoo default behavior)\n"
            "- Order contact only: Only the contact who placed the order"
        ),
    )