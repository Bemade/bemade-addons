from odoo import api, fields, models
from odoo.exceptions import UserError


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def add_blacklist(self):
        self.ensure_one()

        # Create a new blacklist record
        blacklist = self.env['mailcow.blacklist'].create({
            'email': self.email,
        })

        # Assign 'spam' as a closed stage
        spam_stage = self.env.ref('bemade_helpdesk_mailcow_blacklist.helpdesk_stage_spam')

        if spam_stage:
            self.stage_id = spam_stage.id
        else:
            raise UserError(_('The Spam stage does not exist.'))

        return True
