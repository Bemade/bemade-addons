from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    settings = env['ir.config_parameter']
    create_param = settings.get_param('mailcow.create_mailbox')
    sync_param = settings.get_param('mailcow.sync_alias')
    base_url = settings.get_param('mailcow.base_url')
    api_key = settings.get_param('mailcow.api_key')

    if (create_param or sync_param) and (not base_url or not api_key):
        (create_param | sync_param).write({'value': False})
