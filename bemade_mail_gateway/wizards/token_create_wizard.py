# Copyright (C) 2026 Bemade Inc.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Wizard to create a new mail-gateway token.

Flow:

1. Admin opens the wizard (Settings → Bemade → Mail Gateway Tokens →
   Generate Token), enters a label and (optionally) an expiration.
2. Clicks "Generate". The wizard calls
   :meth:`BemadeMailGatewayToken.action_generate`, which creates the
   stored record (sha256 hash only) and returns the raw token.
3. The wizard form re-renders with the raw token displayed in a
   readonly text box, surrounded by an alert reminding the operator
   that this is the only opportunity to copy it.
4. Closing the wizard discards the transient record; the raw token
   is no longer recoverable from anywhere.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TokenCreateWizard(models.TransientModel):
    _name = "bemade.mail_gateway.token.create.wizard"
    _description = "Generate a Bemade Mail Gateway Token"

    name = fields.Char(
        required=True,
        help="Human-readable label (e.g. 'omg-sugar', 'omg-pneumac').",
    )
    description = fields.Text(
        help="Optional notes — what integration uses this token, who owns it.",
    )
    expires_at = fields.Datetime(
        help="Optional expiration. Leave empty for a token that never expires.",
    )

    # Filled after generation; transient + readonly. Never written to disk
    # beyond this wizard's lifetime. Each gets an explicit `string` so
    # they don't collide on the default "Generated Token" label that the
    # field-name auto-derivation would produce.
    generated_token = fields.Char(
        string="Token Value",
        readonly=True,
    )
    generated_token_id = fields.Many2one(
        "bemade.mail_gateway.token",
        string="Token Record",
        readonly=True,
        help="Reference to the created token record (so the user can navigate to it).",
    )

    def action_generate(self) -> dict:
        """Generate the token, store the record, expose the raw value once."""
        self.ensure_one()
        if self.generated_token:
            raise UserError(
                _("This wizard has already generated a token. Close it and start a new one.")
            )
        rec, raw = self.env["bemade.mail_gateway.token"].action_generate(
            name=self.name,
            description=self.description or "",
            expires_at=self.expires_at,
        )
        self.write(
            {
                "generated_token": raw,
                "generated_token_id": rec.id,
            }
        )
        # Re-open the same wizard record so the form reloads with the
        # generated token visible. Odoo's standard pattern for "show me
        # the result of a wizard step in the same modal".
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "name": _("Token Generated — Save It Now"),
            "context": {"wizard_step": "show_token"},
        }

    def action_close(self) -> dict:
        """Close the wizard without further action."""
        return {"type": "ir.actions.act_window_close"}

    @api.model
    def action_open_create_wizard(self) -> dict:
        """Entry point button — opens an empty wizard."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "target": "new",
            "name": _("Generate Mail Gateway Token"),
        }
