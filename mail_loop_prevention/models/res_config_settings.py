# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mail_loop_prevention_enabled = fields.Boolean(
        string="Enable Mail Loop Prevention",
        config_parameter="mail_loop_prevention.enabled",
        default=True,
        help="Prevent auto-reply communication loops between mail servers",
    )

    mail_loop_prevention_block_auto_generated = fields.Boolean(
        string="Block Auto-Generated Emails",
        config_parameter="mail_loop_prevention.block_auto_generated",
        default=False,
        help="Also block emails with Auto-Submitted: auto-generated. "
        "This may block legitimate automated forwards.",
    )

    @api.model
    def _get_param_as_bool(self, key, default=False):
        """Get a config parameter as a boolean.

        Config parameters store booleans as strings "True"/"False";
        this converts them to actual Python booleans.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        value = ICP.get_param(key, default=str(default))
        if isinstance(value, bool):
            return value
        return value in ("True", "true", "1")
