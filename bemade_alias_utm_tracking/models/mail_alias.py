# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MailAlias(models.Model):
    _inherit = "mail.alias"

    track_utm_source = fields.Boolean(
        string="Track UTM Source",
        help="When enabled, records created from inbound mail to this alias "
        "are attributed to the UTM source/medium/campaign configured below "
        "(for any target model that supports UTM tracking, e.g. helpdesk "
        "tickets and CRM leads).",
    )
    utm_source_id = fields.Many2one(
        comodel_name="utm.source",
        string="UTM Source",
        ondelete="set null",
        help="UTM source stamped on records created from inbound mail to this "
        "alias.",
    )
    utm_medium_id = fields.Many2one(
        comodel_name="utm.medium",
        string="UTM Medium",
        ondelete="set null",
        help="Optional UTM medium stamped on records created from inbound mail "
        "to this alias.",
    )
    utm_campaign_id = fields.Many2one(
        comodel_name="utm.campaign",
        string="UTM Campaign",
        ondelete="set null",
        help="Optional UTM campaign stamped on records created from inbound "
        "mail to this alias.",
    )

    # Mapping of the UTM config field on mail.alias -> the field on the target
    # record (utm.mixin convention). Kept as a single source of truth so the
    # creation-values builder and the mail.thread override stay in sync.
    _UTM_ALIAS_TO_RECORD = {
        "utm_source_id": "source_id",
        "utm_medium_id": "medium_id",
        "utm_campaign_id": "campaign_id",
    }

    def _get_utm_creation_values(self):
        """Return the UTM defaults this alias should stamp on a created record.

        Empty dict when tracking is off or no source is configured. Only
        non-empty M2o values are returned, keyed by the *record* field name
        (``source_id`` / ``medium_id`` / ``campaign_id``).
        """
        self.ensure_one()
        if not self.track_utm_source or not self.utm_source_id:
            return {}
        values = {}
        for alias_field, record_field in self._UTM_ALIAS_TO_RECORD.items():
            value = self[alias_field]
            if value:
                values[record_field] = value.id
        return values
