from datetime import timedelta
from typing import TYPE_CHECKING, Optional, cast

from odoo import api, fields, models

if TYPE_CHECKING:
    from odoo.addons.mail.models.mail_activity_mixin import MailActivityMixin


class BaseLateNotificationMixin(models.AbstractModel):
    """Abstract model for late order notifications"""

    _name = "base.late.notification.mixin"
    _description = "Base Late Notification Mixin"

    # Subclasses must override these class attributes or related helpers
    _late_config_prefix: Optional[str] = None  # e.g., "sale" or "purchase"
    _late_activity_note = ""
    _late_activity_summary_default = "Vérifier commande en retard"
    _late_notification_days_default = 5
    # Days to wait after a previous late-notification activity was marked Done
    # before re-creating one while the order is still late.
    _late_renotify_cooldown_days_default = 7

    late_notification_date = fields.Datetime(
        string="Late Notification Date",
        help="Date when a late notification was last sent for this order.",
        copy=False,
    )
    late_days_threshold = fields.Integer(
        string="Late Days Threshold",
        compute="_compute_late_days_threshold",
        help="Number of days an order must be late before notification.",
    )
    is_past_threshold = fields.Boolean(
        string="Past Threshold",
        compute="_compute_is_past_threshold",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
    )

    # -------------------------------------------------------------------------
    # Configuration helpers
    # -------------------------------------------------------------------------

    @api.model
    def _get_config_prefix(self):
        if not self._late_config_prefix:
            raise ValueError(
                "Late notification mixin requires '_late_config_prefix' to be set"
            )
        return self._late_config_prefix

    @api.model
    def _get_config_param_key(self, suffix):
        return f"sale_purchase_late_notification.{self._get_config_prefix()}_{suffix}"

    @api.model
    def _get_config_param(self, suffix, default):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._get_config_param_key(suffix), default)
        )

    @api.model
    def _is_late_notification_enabled(self):
        """Check if late notifications are enabled for this model."""
        enabled = self._get_config_param("enabled", "False")
        if isinstance(enabled, bool):
            return enabled
        return str(enabled).lower() in ("true", "1", "yes")

    @api.model
    def _get_late_activity_summary(self):
        return self._get_config_param(
            "activity_summary", self._late_activity_summary_default
        )

    @api.model
    def _get_late_activity_user_id(self):
        return int(
            self._get_config_param("default_user_id", str(self.env.user.id))
            or self.env.user.id
        )

    @api.model
    def _get_renotify_cooldown_days(self):
        """Number of days to wait after a prior late-notification activity was
        marked Done before re-creating one while the order is still late.

        Configurable per model via the
        ``sale_purchase_late_notification.<prefix>_renotify_cooldown_days``
        config parameter (exposed in the relevant app's settings). Falls back to
        ``_late_renotify_cooldown_days_default``.
        """
        return int(
            self._get_config_param(
                "renotify_cooldown_days",
                str(self._late_renotify_cooldown_days_default),
            )
            or self._late_renotify_cooldown_days_default
        )

    @api.depends("partner_id.commercial_partner_id")
    def _compute_late_days_threshold(self):
        """Compute the number of days an order must be late before notification.

        Uses the commercial partner (company) level setting if available.
        """
        global_threshold = int(
            self._get_config_param(
                "late_days_threshold", str(self._late_notification_days_default)
            )
        )
        for order in self:
            commercial_partner = order.partner_id.commercial_partner_id
            partner_delay = getattr(
                commercial_partner,
                f"{self._get_config_prefix()}_late_notification_delay",
                None,
            )
            order.late_days_threshold = partner_delay or global_threshold

    @api.depends("late_days_threshold")
    def _compute_is_past_threshold(self):
        raise NotImplementedError(
            "Subclasses must implement _compute_is_past_threshold()"
        )

    @api.model
    def _get_activity_type(self):
        """Get the activity type for late order notifications"""
        return self.env.ref("mail.mail_activity_data_todo")

    @api.model
    def _get_late_orders_domain(self):
        """Get the domain to find candidate late orders.

        Relies on the model's is_late field and its _search_is_late method to handle
        the actual late detection logic using stored/searchable fields.

        NB: this no longer filters on ``late_notification_date = False``. Whether an
        already-notified order is *re-notified* is decided per-order by
        :meth:`_should_notify` (idempotent open-activity check + configurable
        re-notification cooldown), which subsumes the old one-shot behaviour.
        """
        return [
            ("is_late", "=", True),
        ]

    @api.model
    def _get_late_orders(self):
        """Find orders that are late and haven't been notified yet.

        Subclasses should override _get_late_order_ids() to use efficient SQL
        that incorporates the threshold check.
        """
        order_ids = self._get_late_order_ids()
        if not order_ids:
            return self.browse()
        return self.browse(order_ids)

    @api.model
    def _get_late_order_ids(self):
        """Get IDs of late orders past threshold. Subclasses should override with SQL."""
        # Fallback: use domain search (less efficient)
        return self.search(self._get_late_orders_domain()).ids

    def _get_open_late_activities(self):
        """Return this order's currently-open late-notification activities.

        ``activity_ids`` only exposes active (not-yet-done) activities, so a match
        here means the user still has an open reminder for this order.
        """
        self.ensure_one()
        activity_type = self._get_activity_type()
        summary = self._get_late_activity_summary()
        return cast("MailActivityMixin", self).activity_ids.filtered(
            lambda act: act.activity_type_id == activity_type
            and act.summary == summary
        )

    def _get_last_late_activity_done_date(self):
        """Return when the most recent late-notification activity for this order
        was marked Done, or ``False`` if none ever was.

        When an activity is marked Done its record is unlinked (or archived), so we
        cannot read it back directly. Instead we read the "activity done" message
        that ``mail.activity._action_done`` posts on the record, identified by its
        activity type and the ``mail.mt_activities`` subtype.
        """
        self.ensure_one()
        activity_type = self._get_activity_type()
        done_subtype = self.env.ref("mail.mt_activities", raise_if_not_found=False)
        done_messages = cast("MailActivityMixin", self).message_ids.filtered(
            lambda msg: msg.mail_activity_type_id == activity_type
            and (not done_subtype or msg.subtype_id == done_subtype)
        )
        if not done_messages:
            return False
        return max(done_messages.mapped("date"))

    def _should_notify(self):
        """Decide whether to (re-)create a late activity for this order now.

        - Skip if an open late activity already exists (idempotent — never stack).
        - Notify if the order was never notified before.
        - Otherwise re-notify only once the configured cooldown has elapsed since
          the previous late activity was marked Done (subsumes the one-shot rule).
        """
        self.ensure_one()
        if self._get_open_late_activities():
            return False
        if not self.late_notification_date:
            return True
        closed_on = self._get_last_late_activity_done_date()
        if not closed_on:
            # Previously notified but no done-message found (e.g. the activity is
            # gone yet was not marked done via the standard flow). Fall back to the
            # last notification timestamp so the cooldown still applies.
            closed_on = self.late_notification_date
        cooldown = timedelta(days=self._get_renotify_cooldown_days())
        return fields.Datetime.now() - closed_on >= cooldown

    @api.model
    def create_late_activities(self):
        """Create (or re-create) activities for late orders.

        Re-creation respects a configurable cooldown after the previous activity
        was marked Done, so a still-late order keeps reminding the user instead of
        firing only once.
        """
        late_orders = self._get_late_orders()
        if not late_orders:
            return

        activity_vals = {
            "activity_type_id": self._get_activity_type().id,
            "summary": self._get_late_activity_summary(),
            "note": self._get_activity_note(),
            "user_id": self._get_late_activity_user_id(),
            "date_deadline": fields.Date.today() + timedelta(days=1),
        }

        for order in late_orders:
            if not order.is_past_threshold:
                continue
            if not order._should_notify():
                continue
            cast("MailActivityMixin", order).activity_schedule(**activity_vals)
            order.late_notification_date = fields.Datetime.now()

    @api.model
    def _get_activity_note(self):
        """Get the note to include in the activity"""
        return self._late_activity_note

    # -------------------------------------------------------------------------
    # Cron helper
    # -------------------------------------------------------------------------

    @api.model
    def _cron_create_late_activities(self):
        """Cron job entry point - only runs if notifications are enabled."""
        if not self._is_late_notification_enabled():
            return
        self.create_late_activities()
