from odoo import _, fields, models
from odoo.exceptions import UserError


class ConversationInboxReassignWizard(models.TransientModel):
    """GTD 'reassign' dialog (task #3965, AC6g): hand an inbox item to a
    colleague and/or a team. Filing is idempotent (_capture_or_find): if
    this item was already captured by an earlier action, reassigns that
    same conversation instead of filing a duplicate.
    """

    _name = "conversation.inbox.reassign.wizard"
    _description = "Reassign Inbox Item"

    transport_id = fields.Many2one(
        "conversation.transport", required=True, readonly=True
    )
    external_id = fields.Char(required=True, readonly=True)
    user_id = fields.Many2one("res.users", string="Assign To")
    team_id = fields.Many2one("mail.conversation.team", string="Team")

    def action_reassign(self):
        self.ensure_one()
        if not self.user_id and not self.team_id:
            raise UserError(_("Pick a user or a team to reassign to."))
        conversation = self.env["mail.conversation"]._capture_or_find(
            self.transport_id, self.external_id
        )
        conversation.action_reassign(
            user=self.user_id or None, team=self.team_id or None
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "mail.conversation",
            "res_id": conversation.id,
            "view_mode": "form",
            "target": "current",
        }
