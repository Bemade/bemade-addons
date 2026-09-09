from odoo import fields, models


class MailConversationTeam(models.Model):
    """A team that owns conversations. Standalone: NOT ``crm.team``,
    ``helpdesk.team`` or ``discuss.channel``'s notion of a team -- those
    model different concerns (pipelines, SLAs, discuss membership) that
    conversation triage does not need.
    """

    _name = "mail.conversation.team"
    _description = "Conversation Team"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    member_ids = fields.Many2many(
        "res.users",
        "mail_conversation_team_res_users_rel",
        "team_id",
        "user_id",
        string="Members",
    )
    default_user_id = fields.Many2one(
        "res.users",
        string="Default Assignee",
    )
    inbox_transport_ids = fields.Many2many(
        "conversation.transport",
        "mail_conversation_team_transport_rel",
        "team_id",
        "transport_id",
        string="Inbox Transports",
        help="Transports this team monitors (forward-compatibility for "
        "later epics; not enforced here).",
    )
    conversation_ids = fields.One2many(
        "mail.conversation",
        "team_id",
        string="Conversations",
    )

    _sql_constraints = [
        ("name_uniq", "unique(name)", "A team with this name already exists."),
    ]
