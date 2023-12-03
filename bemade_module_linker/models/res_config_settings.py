from odoo import models, fields, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    root_repos_directory = fields.Char(string="Root Repos Directory")
    enabled_addons_directory = fields.Char(string="Enabled Addons Directory")
