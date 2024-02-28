# Copyright Bemade.org
from odoo import models, fields, api


class MailWizardInviteDefault(models.TransientModel):
    _inherit = 'mail.wizard.invite'

    send_mail = fields.Boolean(
        default=False,
        help="If true, an invitation email will be sent to the recipient"
    )
