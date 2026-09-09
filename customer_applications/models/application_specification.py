from odoo import models, fields, api, Command, _
from odoo.exceptions import ValidationError


class PartnerApplicationSpecification(models.Model):
    _name = "partner.application.specification"
    _description = "Partner Application Specification"
    _inherit = ["mail.thread", "mail.activity.mixin", "incrementing.sequence.mixin"]
    _sequence_group = "application_id"

    key_id = fields.Many2one(
        comodel_name="partner.application.specification.key",
        tracking=1,
        ondelete="restrict",
        domain="[('id', 'in', allowed_specification_keys)]",
        string="Specification Name",
        required=True,
    )
    name = fields.Char(
        related="key_id.name",
    )
    value = fields.Text(
        tracking=2,
    )
    application_id = fields.Many2one(
        comodel_name="partner.application",
        tracking=1,
        ondelete="cascade",
    )
    allowed_specification_keys = fields.Many2many(
        related="application_id.application_type_id.allowed_specification_keys",
    )

    @api.model_create_multi
    def create(self, vals_list):
        # Auto-allow each new key on its application type *before* creating the
        # spec records: the `_constrain_key_id` constraint is validated during
        # `_create` itself (via `_validate_fields`), not on a later flush, so the
        # key must already be in the type's allowed list by the time super runs.
        for vals in vals_list:
            self._allow_key_on_type(
                vals.get("application_id"), vals.get("key_id")
            )
        return super().create(vals_list)

    def write(self, vals):
        # Same timing: link the (possibly changed) key before super so the
        # constraint passes when it validates the write.
        if vals.get("key_id"):
            application_type = (
                self.application_id.application_type_id
            )
            for app_type in application_type:
                self._allow_key_on_type(app_type.id, vals["key_id"])
        return super().write(vals)

    @api.model
    def _allow_key_on_type(self, application_id, key_id):
        """Ensure ``key_id`` is in the application type's allowed keys.

        Resolves the type from ``application_id`` and links ``key_id`` into its
        ``allowed_specification_keys`` when missing, so the
        ``_constrain_key_id`` constraint passes. Idempotent: ``Command.link`` is
        additive and a no-op for an already-allowed key. Skips silently when the
        application, type, or key is absent (the ``required`` field / constraint
        govern those cases).
        """
        if not application_id or not key_id:
            return
        application = self.env["partner.application"].browse(application_id)
        application_type = application.application_type_id
        if not application_type:
            return
        key = self.env["partner.application.specification.key"].browse(key_id)
        if key not in application_type.allowed_specification_keys:
            application_type.allowed_specification_keys = [Command.link(key.id)]

    @api.constrains("key_id")
    def _constrain_key_id(self):
        for rec in self:
            if rec.key_id not in rec.allowed_specification_keys:
                raise ValidationError(
                    _(
                        f"Key '{rec.key_id.name}' is not allowed for this application type."
                    )
                )
