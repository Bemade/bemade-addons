"""Tests for the configurable re-notification cadence.

Acceptance criteria covered:
  1. A still-late order whose previous late-notification activity was marked Done
     re-notifies once the configured cooldown has elapsed (the fix for the
     one-shot bug).
  2. Before the cooldown elapses, no new activity is created (cadence respected).
  3. Idempotent: while a late activity is still open, the cron never stacks a
     second one.
  4. Both sale.order and purchase.order are covered (the mixin abstracts both).
  5. The cooldown is a real, per-model configurable setting (config parameter).
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


class _LateRenotifyCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.product = cls.env["product.product"].create(
            {"name": "Test Product", "type": "consu"}
        )

    def _mark_late_activity_done(self, order):
        """Mark the order's open late-notification activity as Done.

        Mirrors the user clicking "Done": the activity record is removed and an
        "activity done" message is posted on the record (which is how the cron
        later detects the closure timestamp).
        """
        activities = order._get_open_late_activities()
        self.assertTrue(activities, "Expected an open late activity to mark Done")
        activities.action_done()

    def _backdate_closure(self, order, days):
        """Move the most recent activity-done message back ``days`` days so the
        cooldown logic sees the closure as having happened in the past."""
        done_subtype = self.env.ref("mail.mt_activities")
        activity_type = order._get_activity_type()
        done_messages = order.message_ids.filtered(
            lambda m: m.mail_activity_type_id == activity_type
            and m.subtype_id == done_subtype
        )
        self.assertTrue(done_messages, "Expected an activity-done message")
        done_messages.write({"date": fields.Datetime.now() - timedelta(days=days)})


@tagged("post_install", "-at_install")
class TestSaleRenotifyCadence(_LateRenotifyCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Customer"})
        cls.user = cls.env["res.users"].create(
            {
                "name": "Sale Renotify User",
                "login": "test_renotify_sale_user",
                "email": "renotify_sale@example.com",
            }
        )
        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("sale_purchase_late_notification.sale_enabled", "True")
        ICP.set_param("sale_purchase_late_notification.sale_late_days_threshold", "5")
        ICP.set_param(
            "sale_purchase_late_notification.sale_default_user_id", str(cls.user.id)
        )
        ICP.set_param(
            "sale_purchase_late_notification.sale_renotify_cooldown_days", "7"
        )

    def _create_late_sale_order(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "client_order_ref": "test",
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )
        order.with_context(skip_tax_warning=True).action_confirm()
        order.order_line.expected_ship_date = fields.Date.today() - timedelta(days=6)
        return order

    def test_cooldown_is_configurable(self):
        """The cooldown is read from the config parameter, not hard-coded."""
        self.env["ir.config_parameter"].sudo().set_param(
            "sale_purchase_late_notification.sale_renotify_cooldown_days", "13"
        )
        self.assertEqual(
            self.env["sale.order"]._get_renotify_cooldown_days(),
            13,
            "Cooldown must come from the config parameter",
        )

    def test_renotifies_after_cooldown_post_done(self):
        """Still-late order re-notifies once cooldown elapsed after prior Done."""
        order = self._create_late_sale_order()

        self.env["sale.order"]._cron_create_late_activities()
        self.assertEqual(len(order.activity_ids), 1, "First activity should be created")

        # User clears the reminder; order stays late.
        self._mark_late_activity_done(order)
        self.assertEqual(len(order.activity_ids), 0, "Activity cleared after Done")

        # Closure happened 8 days ago > 7-day cooldown -> re-notify.
        self._backdate_closure(order, days=8)
        self.env["sale.order"]._cron_create_late_activities()
        self.assertEqual(
            len(order.activity_ids),
            1,
            "A renewed activity should be created after the cooldown",
        )

    def test_no_renotify_before_cooldown(self):
        """No new activity while the cooldown since the prior Done has not elapsed."""
        order = self._create_late_sale_order()
        self.env["sale.order"]._cron_create_late_activities()
        self._mark_late_activity_done(order)

        # Closure only 2 days ago < 7-day cooldown -> no re-notify.
        self._backdate_closure(order, days=2)
        self.env["sale.order"]._cron_create_late_activities()
        self.assertEqual(
            len(order.activity_ids),
            0,
            "No renewed activity should be created before the cooldown elapses",
        )

    def test_idempotent_while_activity_open(self):
        """Cron never stacks a second activity while one is still open."""
        order = self._create_late_sale_order()
        self.env["sale.order"]._cron_create_late_activities()
        self.env["sale.order"]._cron_create_late_activities()
        self.assertEqual(
            len(order.activity_ids),
            1,
            "Only one open activity should exist while it is unresolved",
        )


@tagged("post_install", "-at_install")
class TestPurchaseRenotifyCadence(_LateRenotifyCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Vendor"})
        cls.user = cls.env["res.users"].create(
            {
                "name": "Purchase Renotify User",
                "login": "test_renotify_purchase_user",
                "email": "renotify_purchase@example.com",
            }
        )
        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("sale_purchase_late_notification.purchase_enabled", "True")
        ICP.set_param(
            "sale_purchase_late_notification.purchase_late_days_threshold", "5"
        )
        ICP.set_param(
            "sale_purchase_late_notification.purchase_default_user_id", str(cls.user.id)
        )
        ICP.set_param(
            "sale_purchase_late_notification.purchase_renotify_cooldown_days", "7"
        )

    def _create_late_purchase_order(self):
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 1,
                            "price_unit": 100,
                            "name": self.product.name,
                            "date_planned": fields.Datetime.now()
                            - timedelta(days=6),
                        },
                    )
                ],
            }
        )
        order.button_confirm()
        return order

    def test_renotifies_after_cooldown_post_done(self):
        """Still-late PO re-notifies once cooldown elapsed after prior Done."""
        order = self._create_late_purchase_order()

        self.env["purchase.order"]._cron_create_late_activities()
        self.assertEqual(len(order.activity_ids), 1, "First activity should be created")

        self._mark_late_activity_done(order)
        self.assertEqual(len(order.activity_ids), 0, "Activity cleared after Done")

        self._backdate_closure(order, days=8)
        self.env["purchase.order"]._cron_create_late_activities()
        self.assertEqual(
            len(order.activity_ids),
            1,
            "A renewed activity should be created after the cooldown",
        )

    def test_no_renotify_before_cooldown(self):
        """No new PO activity while the cooldown since the prior Done has not elapsed."""
        order = self._create_late_purchase_order()
        self.env["purchase.order"]._cron_create_late_activities()
        self._mark_late_activity_done(order)

        self._backdate_closure(order, days=2)
        self.env["purchase.order"]._cron_create_late_activities()
        self.assertEqual(
            len(order.activity_ids),
            0,
            "No renewed activity should be created before the cooldown elapses",
        )

    def test_idempotent_while_activity_open(self):
        """Cron never stacks a second PO activity while one is still open."""
        order = self._create_late_purchase_order()
        self.env["purchase.order"]._cron_create_late_activities()
        self.env["purchase.order"]._cron_create_late_activities()
        self.assertEqual(
            len(order.activity_ids),
            1,
            "Only one open activity should exist while it is unresolved",
        )
