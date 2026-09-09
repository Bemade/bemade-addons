from odoo.tests import TransactionCase, Form, tagged
from datetime import datetime, timedelta


@tagged("-at_install", "post_install")
class TestMailThread(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_alternate_recipient_is_notified(self):
        user_1, user_2 = self.env["res.users"].create(
            [
                {
                    "name": "Test 1",
                    "login": "test1",
                    "notification_type": "inbox",
                },
                {
                    "name": "Test 2",
                    "login": "test2",
                    "notification_type": "inbox",
                },
            ]
        )
        empl_1, empl_2 = self.env["hr.employee"].create(
            [
                {"name": "Test 1", "user_id": user_1.id},
                {"name": "Test 2", "user_id": user_2.id},
            ]
        )
        leave = self.env["hr.leave"].create(
            {
                "employee_id": empl_1.id,
                "request_date_from": datetime.now() - timedelta(days=1),
                "request_date_to": datetime.now() + timedelta(days=1),
                "holiday_status_id": self.env.ref(
                    "hr_holidays.holiday_status_unpaid"
                ).id,
                "alternate_follower_id": user_2.id,
            }
        )
        leave.action_approve()
        if leave.state == "validate1":
            leave.action_validate()
        comment = self.env.ref("mail.mt_comment")
        partner = empl_1.user_partner_id
        partner.message_subscribe([partner.id], [comment.id])
        body = f"@{user_1.name} Something something"
        message_id = partner.message_post(
            body=body,
            message_type="comment",
            subtype_id=comment.id,
        )

        notifications = self.env["mail.notification"].search(
            [
                ["res_partner_id", "=", empl_2.user_partner_id.id],
            ]
        )
        self.assertEqual(len(notifications), 2)
