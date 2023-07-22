from odoo import api, fields, models
from odoo.exceptions import UserError
import re

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def action_add_blacklist(self):
        self.ensure_one()
        email_regex = r'<([^<>]+)>'

        email_to_blacklist = re.findall(email_regex, self.email)[0]

        # Create a new blacklist record
        blacklist = self.env['mail.mailcow.blacklist'].create({
            'email': email_to_blacklist,
        })

        # Assign 'spam' as a closed stage
        spam_stage = self.env.ref('bemade_helpdesk_mailcow_blacklist.helpdesk_stage_spam')

        if spam_stage:
            self.stage_id = spam_stage.id
        else:
            raise UserError(_('The Spam stage does not exist.'))

        return True
