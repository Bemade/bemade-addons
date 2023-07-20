from odoo import fields, models, api
from odoo.exceptions import ValidationError
import os


class ResModuleLinks(models.Model):
    _name = 'res.modules.links'
    _description = 'Module Links'

    name = fields.Char('Name', required=True)
    module_id = fields.Many2one('ir.module.module', string='Module')
    active = fields.Boolean(default=False)
    repo_name = fields.Char('Repo Name', required=True)

    @api.onchange('active')
    def on_change_active(self):
        params = self.env['ir.config_parameter'].sudo()
        from_dir = params.get_param('root_repos_directory')[0],
        to_dir = params.get_param('enabled_addons_directory')[0],

        if self.active:
            os.unlink(os.getcwd() + self.repo_name + '/' + self.name)
            self.module_id.state = 'installed'
        else:
            if self.module_id.state == 'installed':
                raise ValidationError('You must uninstall the module before deactivating it.')
            else:
                os.symlink(os.getcwd() + self.repo_name + '/' + self.name, os.getcwd() + self.repo_name + '/' + self.name)
