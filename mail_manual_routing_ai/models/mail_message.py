# -*- coding: utf-8 -*-
import json
import logging
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    """Extend mail.message with AI classification confidence."""
    _inherit = 'mail.message'

    classification_confidence = fields.Float(
        string="AI Confidence",
        help="Confidence level of the AI classification (0-100%)",
        digits=(5, 2),
    )
    ai_classification_date = fields.Datetime(
        string="AI Classification Date",
        help="When this message was classified by AI",
    )

    def action_ai_classify(self):
        """Manually trigger AI classification for selected messages."""
        classified_count = 0
        for message in self:
            if message._ai_classify_message():
                classified_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('AI Classification'),
                'message': _('%d message(s) classified successfully') % classified_count,
                'type': 'success',
                'sticky': False,
            }
        }

    def _ai_classify_message(self):
        """
        Classify a single message using OpenWebUI AI.

        Returns:
            bool: True if classification was successful, False otherwise
        """
        self.ensure_one()

        if not self.is_unattached:
            _logger.info("Message %s is not unattached, skipping AI classification", self.id)
            return False

        # Get OpenWebUI configuration
        ICP = self.env['ir.config_parameter'].sudo()
        openwebui_url = ICP.get_param('mail_manual_routing_ai.openwebui_url')
        openwebui_api_key = ICP.get_param('mail_manual_routing_ai.openwebui_api_key')
        openwebui_model = ICP.get_param('mail_manual_routing_ai.openwebui_model', 'glm-5:cloud')

        if not openwebui_url:
            raise UserError(_("OpenWebUI URL is not configured. Please configure it in Settings > General Settings > Lost Messages AI."))

        # Get available subcategories
        subcategories = self.env['lost.message.subcategory'].search([('active', '=', True)])
        if not subcategories:
            _logger.warning("No active subcategories found")
            return False

        # Build classification prompt
        prompt = self._build_classification_prompt(subcategories)

        try:
            # Call OpenWebUI API
            response = self._call_openwebui_api(
                url=openwebui_url,
                api_key=openwebui_api_key,
                model=openwebui_model,
                prompt=prompt
            )

            # Parse response and update message
            return self._process_ai_response(response, subcategories)

        except Exception as e:
            _logger.error("AI classification failed for message %s: %s", self.id, str(e))
            return False

    def _build_classification_prompt(self, subcategories):
        """Build the prompt for AI classification."""
        categories_desc = "\n".join([
            f"- {cat.code}: {cat.name} - {cat.description}"
            for cat in subcategories
        ])

        message_content = self.body or ""
        message_subject = self.subject or ""
        message_from = self.email_from or ""

        prompt = f"""You are an email classifier for a business email system. Classify the following email into one of the categories below.

Available categories:
{categories_desc}

Email details:
- From: {message_from}
- Subject: {message_subject}
- Body: {message_content[:1000]}

Analyze this email and respond ONLY with a JSON object in this exact format:
{{"category": "category_code", "confidence": 85.5, "reasoning": "brief explanation"}}

The category must be one of the codes listed above.
The confidence should be a number between 0 and 100.
Keep the reasoning brief (1-2 sentences).
"""
        return prompt

    def _call_openwebui_api(self, url, api_key, model, prompt):
        """
        Call OpenWebUI API for classification.

        Args:
            url (str): OpenWebUI base URL
            api_key (str): API key for authentication
            model (str): Model name to use
            prompt (str): Classification prompt

        Returns:
            dict: API response
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        # OpenWebUI uses OpenAI-compatible API
        api_endpoint = f"{url.rstrip('/')}/api/chat/completions"

        payload = {
            'model': model,
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.1,  # Low temperature for more consistent classification
            'max_tokens': 200,
        }

        _logger.info("Calling OpenWebUI API at %s with model %s", api_endpoint, model)

        response = requests.post(
            api_endpoint,
            headers=headers,
            json=payload,
            timeout=30
        )

        response.raise_for_status()
        return response.json()

    def _process_ai_response(self, response, subcategories):
        """
        Process AI response and update message classification.

        Args:
            response (dict): OpenWebUI API response
            subcategories (recordset): Available subcategories

        Returns:
            bool: True if successful
        """
        try:
            # Extract content from OpenAI-compatible response
            content = response['choices'][0]['message']['content'].strip()

            # Try to parse JSON from content
            # Sometimes the AI adds markdown code blocks, so we need to clean it
            if content.startswith('```'):
                # Remove markdown code blocks
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)

            category_code = result.get('category')
            confidence = float(result.get('confidence', 0))
            reasoning = result.get('reasoning', '')

            # Find matching subcategory
            subcategory = subcategories.filtered(lambda c: c.code == category_code)

            if not subcategory:
                _logger.warning("AI returned unknown category: %s", category_code)
                return False

            # Update message
            self.write({
                'lost_subcategory_id': subcategory[0].id,
                'classification_confidence': confidence,
                'ai_classification_date': fields.Datetime.now(),
                'lost_comments': (self.lost_comments or '') + f"\n\nAI Classification ({fields.Datetime.now()}):\n{reasoning}"
            })

            _logger.info(
                "Message %s classified as %s with %.2f%% confidence: %s",
                self.id, category_code, confidence, reasoning
            )

            return True

        except (KeyError, json.JSONDecodeError, ValueError) as e:
            _logger.error("Failed to parse AI response: %s\nResponse: %s", str(e), response)
            return False

    @api.model
    def create(self, vals):
        """Auto-classify unattached messages on creation if enabled."""
        message = super().create(vals)

        # Check if auto-classification is enabled
        auto_classify = self.env['ir.config_parameter'].sudo().get_param(
            'mail_manual_routing_ai.auto_classify',
            default='False'
        )

        if auto_classify == 'True' and message.is_unattached:
            # Classify in a separate transaction to avoid blocking message creation
            self.env.cr.commit()
            try:
                message._ai_classify_message()
                self.env.cr.commit()
            except Exception as e:
                _logger.error("Auto-classification failed for message %s: %s", message.id, str(e))
                self.env.cr.rollback()

        return message
