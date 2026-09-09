# -*- coding: utf-8 -*-
from odoo import fields, models, _


class ResConfigSettings(models.TransientModel):
    """Add OpenWebUI configuration to settings."""
    _inherit = 'res.config.settings'

    openwebui_url = fields.Char(
        string="OpenWebUI URL",
        help="Base URL of your OpenWebUI server (e.g., http://localhost:3000)",
        config_parameter='mail_manual_routing_ai.openwebui_url',
    )

    openwebui_api_key = fields.Char(
        string="OpenWebUI API Key",
        help="API key for authentication (optional if server doesn't require it)",
        config_parameter='mail_manual_routing_ai.openwebui_api_key',
    )

    openwebui_model = fields.Char(
        string="Model Name",
        help="Name of the LLM model to use (e.g., glm-5:cloud, llama3, mistral, gpt-4)",
        default='glm-5:cloud',
        config_parameter='mail_manual_routing_ai.openwebui_model',
    )

    auto_classify_messages = fields.Boolean(
        string="Auto-Classify New Messages",
        help="Automatically classify new unattached messages using AI",
        config_parameter='mail_manual_routing_ai.auto_classify',
    )

    min_confidence_threshold = fields.Float(
        string="Minimum Confidence Threshold",
        help="Minimum confidence level (0-100) to auto-apply classification. "
             "Classifications below this threshold will be suggested but not applied automatically.",
        default=80.0,
        config_parameter='mail_manual_routing_ai.min_confidence',
    )
