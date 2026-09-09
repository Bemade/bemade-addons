from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Sale order late notification settings
    sale_late_notification_enabled = fields.Boolean(
        string="Enable Late Sale Order Notifications",
        default=False,
        config_parameter="sale_purchase_late_notification.sale_enabled",
        help="Enable automatic notifications for late sale orders",
    )
    sale_late_notification_days = fields.Integer(
        string="Days Before Notification (Sales)",
        default=5,
        config_parameter="sale_purchase_late_notification.sale_late_days_threshold",
        help="Number of days after the expected date before a sale order is considered late enough to notify",
    )
    sale_late_activity_summary = fields.Char(
        string="Activity Summary (Sales)",
        default="Vérifier commande en retard",
        config_parameter="sale_purchase_late_notification.sale_activity_summary",
        help="Default summary for late sale order activities",
    )
    sale_late_activity_user_id = fields.Many2one(
        "res.users",
        string="Responsible User (Sales)",
        config_parameter="sale_purchase_late_notification.sale_default_user_id",
        help="Default user responsible for handling late sale orders",
    )
    sale_late_renotify_cooldown_days = fields.Integer(
        string="Re-notification Cooldown (Sales)",
        default=7,
        config_parameter="sale_purchase_late_notification.sale_renotify_cooldown_days",
        help="Number of days to wait after a late sale order reminder is marked "
        "Done before a new reminder is created while the order is still late",
    )

    # Purchase order late notification settings
    purchase_late_notification_enabled = fields.Boolean(
        string="Enable Late Purchase Order Notifications",
        default=False,
        config_parameter="sale_purchase_late_notification.purchase_enabled",
        help="Enable automatic notifications for late purchase orders",
    )
    purchase_late_notification_days = fields.Integer(
        string="Days Before Notification (Purchases)",
        default=5,
        config_parameter="sale_purchase_late_notification.purchase_late_days_threshold",
        help="Number of days after the planned date before a purchase order is considered late enough to notify",
    )
    purchase_late_activity_summary = fields.Char(
        string="Activity Summary (Purchases)",
        default="Vérifier commande en retard",
        config_parameter="sale_purchase_late_notification.purchase_activity_summary",
        help="Default summary for late purchase order activities",
    )
    purchase_late_activity_user_id = fields.Many2one(
        "res.users",
        string="Responsible User (Purchases)",
        config_parameter="sale_purchase_late_notification.purchase_default_user_id",
        help="Default user responsible for handling late purchase orders",
    )
    purchase_late_renotify_cooldown_days = fields.Integer(
        string="Re-notification Cooldown (Purchases)",
        default=7,
        config_parameter="sale_purchase_late_notification.purchase_renotify_cooldown_days",
        help="Number of days to wait after a late purchase order reminder is "
        "marked Done before a new reminder is created while the order is still late",
    )
