from odoo import _, fields, models
from odoo.exceptions import UserError


class ConversationInboxCaptureWizard(models.TransientModel):
    """The GTD funnel's primary capture dialog (task #3965, AC6 a/b/c/g):
    file a browsable inbox item as a new conversation, thread it into an
    existing one, or link it to any business record -- optionally
    reassigning in the same step. Quiet capture (AC7/AC8): posts an
    internal note, never re-notifies the original recipients, and maps
    the correspondent to the From partner, not the acting user.
    """

    _name = "conversation.inbox.capture.wizard"
    _description = "Capture Inbox Item"

    transport_id = fields.Many2one(
        "conversation.transport", required=True, readonly=True
    )
    external_id = fields.Char(required=True, readonly=True)
    subject = fields.Char(readonly=True)

    mode = fields.Selection(
        [
            ("new", "New Conversation"),
            ("existing", "Add to Existing Conversation"),
            ("link", "Link to a Record"),
        ],
        default="new",
        required=True,
    )
    conversation_id = fields.Many2one(
        "mail.conversation", string="Existing Conversation"
    )
    res_model_id = fields.Many2one("ir.model", string="Record Model")
    res_id = fields.Integer(string="Record ID")

    user_id = fields.Many2one("res.users", string="Assign To")
    team_id = fields.Many2one("mail.conversation.team", string="Team")

    def _get_link_target(self):
        self.ensure_one()
        if not self.res_model_id or not self.res_id:
            raise UserError(_("Pick a record to link this captured item to."))
        target = self.env[self.res_model_id.model].browse(self.res_id)
        if not target.exists():
            raise UserError(_("That record could not be found."))
        return target

    def action_capture(self):
        self.ensure_one()
        target = False
        if self.mode == "existing":
            if not self.conversation_id:
                raise UserError(
                    _("Pick an existing conversation to add this item to.")
                )
            target = self.conversation_id
        elif self.mode == "link":
            target = self._get_link_target()

        raw = self.transport_id._fetch(self.external_id)
        stub = self.transport_id._normalize(raw)
        conversation = self.env["mail.conversation"]._capture_stub(
            self.transport_id, stub, mode=self.mode, target=target
        )
        if self.user_id or self.team_id:
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
