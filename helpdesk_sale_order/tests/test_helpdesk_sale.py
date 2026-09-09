from odoo.tests import TransactionCase, tagged
from odoo import Command


@tagged("post_install", "-at_install")
class TestHelpdeskSale(TransactionCase):
    def test_convert_ticket_to_sale_order_moves_messages(self):
        # User needs to be part of a sales team, so set that up first
        sale_team = self.env.ref("sales_team.crm_team_1")
        helpdesk_team = self.env.ref("helpdesk.helpdesk_team1")
        helpdesk_team.use_sale_orders = True
        self.env.user.sale_team_id = sale_team

        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Test Ticket",
                "description": "Test description",
                "partner_id": self.env.ref("base.res_partner_2").id,
                "user_id": self.env.user.id,
                "team_id": helpdesk_team.id,
            }
        )
        ticket.message_post(body="This is a test email message")
        ticket.message_post(body="This is another message")
        ticket.message_post(body="This is a comment.", message_type="comment")

        num_messages = len(ticket.message_ids)
        self.assertGreaterEqual(num_messages, 3)
        messages = ticket.message_ids

        action = ticket.action_convert_to_sale_order()
        so = self.env["sale.order"].browse(action["res_id"])

        for message in messages:
            self.assertIn(message.body, so.message_ids.mapped("body"))
        self.assertFalse(ticket.active)

    def test_convert_ticket_to_sale_order_moves_activities(self):
        # User needs to be part of a sales team, so set that up first
        sale_team = self.env.ref("sales_team.crm_team_1")
        helpdesk_team = self.env.ref("helpdesk.helpdesk_team1")
        helpdesk_team.use_sale_orders = True
        self.env.user.sale_team_id = sale_team

        ticket = self.env["helpdesk.ticket"].create(
            {
                "name": "Test Ticket",
                "description": "Test description",
                "partner_id": self.env.ref("base.res_partner_2").id,
                "user_id": self.env.user.id,
                "team_id": helpdesk_team.id,
            }
        )
        activity = self.env["mail.activity"].create(
            {
                "activity_type_id": self.env.ref("mail.mail_activity_data_call").id,
                "res_model_id": self.env.ref("helpdesk.model_helpdesk_ticket").id,
                "res_id": ticket.id,
                "user_id": self.env.user.id,
            }
        )

        action = ticket.action_convert_to_sale_order()
        self.env.invalidate_all(flush=True)
        so = self.env["sale.order"].browse(action["res_id"])

        self.assertIn(activity, so.activity_ids)
