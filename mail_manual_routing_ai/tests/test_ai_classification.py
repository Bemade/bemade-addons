# -*- coding: utf-8 -*-
import json
from unittest.mock import patch, MagicMock
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestAIClassification(TransactionCase):
    """Test AI classification functionality."""

    def setUp(self):
        super().setUp()

        # Create test subcategories
        self.subcategory_spam = self.env['lost.message.subcategory'].create({
            'name': 'Spam',
            'code': 'spam',
            'description': 'Spam messages',
        })

        self.subcategory_legitimate = self.env['lost.message.subcategory'].create({
            'name': 'Legitimate',
            'code': 'legitimate',
            'description': 'Legitimate messages',
        })

        # Create test message
        self.test_message = self.env['mail.message'].create({
            'subject': 'Test spam message',
            'body': '<p>Buy now! Limited offer!</p>',
            'email_from': 'spam@example.com',
            'is_unattached': True,
        })

        # Set configuration parameters
        self.env['ir.config_parameter'].sudo().set_param(
            'mail_manual_routing_ai.openwebui_url',
            'http://localhost:3000'
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'mail_manual_routing_ai.openwebui_model',
            'llama3'
        )

    def test_build_classification_prompt(self):
        """Test that classification prompt is built correctly."""
        subcategories = self.subcategory_spam | self.subcategory_legitimate
        prompt = self.test_message._build_classification_prompt(subcategories)

        self.assertIn('spam: Spam', prompt)
        self.assertIn('legitimate: Legitimate', prompt)
        self.assertIn('Test spam message', prompt)
        self.assertIn('spam@example.com', prompt)
        self.assertIn('Buy now', prompt)

    @patch('requests.post')
    def test_call_openwebui_api(self, mock_post):
        """Test OpenWebUI API call."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': '{"category": "spam", "confidence": 95.5, "reasoning": "Promotional content"}'
                }
            }]
        }
        mock_post.return_value = mock_response

        # Call API
        result = self.test_message._call_openwebui_api(
            url='http://localhost:3000',
            api_key=None,
            model='llama3',
            prompt='Test prompt'
        )

        # Verify API was called correctly
        self.assertTrue(mock_post.called)
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], 'http://localhost:3000/api/chat/completions')
        self.assertEqual(call_args[1]['json']['model'], 'llama3')

        # Verify response
        self.assertIn('choices', result)

    def test_process_ai_response_success(self):
        """Test processing successful AI response."""
        response = {
            'choices': [{
                'message': {
                    'content': '{"category": "spam", "confidence": 95.5, "reasoning": "Promotional content"}'
                }
            }]
        }

        subcategories = self.subcategory_spam | self.subcategory_legitimate
        result = self.test_message._process_ai_response(response, subcategories)

        self.assertTrue(result)
        self.assertEqual(self.test_message.lost_subcategory_id, self.subcategory_spam)
        self.assertEqual(self.test_message.classification_confidence, 95.5)
        self.assertTrue(self.test_message.ai_classification_date)
        self.assertIn('Promotional content', self.test_message.lost_comments)

    def test_process_ai_response_with_markdown(self):
        """Test processing AI response with markdown code blocks."""
        response = {
            'choices': [{
                'message': {
                    'content': '```json\n{"category": "spam", "confidence": 90.0, "reasoning": "Ad content"}\n```'
                }
            }]
        }

        subcategories = self.subcategory_spam | self.subcategory_legitimate
        result = self.test_message._process_ai_response(response, subcategories)

        self.assertTrue(result)
        self.assertEqual(self.test_message.lost_subcategory_id, self.subcategory_spam)
        self.assertEqual(self.test_message.classification_confidence, 90.0)

    def test_process_ai_response_unknown_category(self):
        """Test processing AI response with unknown category."""
        response = {
            'choices': [{
                'message': {
                    'content': '{"category": "unknown_category", "confidence": 85.0, "reasoning": "Test"}'
                }
            }]
        }

        subcategories = self.subcategory_spam | self.subcategory_legitimate
        result = self.test_message._process_ai_response(response, subcategories)

        self.assertFalse(result)
        self.assertFalse(self.test_message.lost_subcategory_id)

    def test_process_ai_response_invalid_json(self):
        """Test processing AI response with invalid JSON."""
        response = {
            'choices': [{
                'message': {
                    'content': 'This is not valid JSON'
                }
            }]
        }

        subcategories = self.subcategory_spam | self.subcategory_legitimate
        result = self.test_message._process_ai_response(response, subcategories)

        self.assertFalse(result)

    @patch.object(type(env['mail.message']), '_call_openwebui_api')
    def test_ai_classify_message_no_config(self, mock_api):
        """Test classification fails without OpenWebUI URL configured."""
        # Remove configuration
        self.env['ir.config_parameter'].sudo().set_param(
            'mail_manual_routing_ai.openwebui_url',
            ''
        )

        with self.assertRaises(UserError):
            self.test_message._ai_classify_message()

    def test_action_ai_classify(self):
        """Test manual AI classification action."""
        with patch.object(type(self.test_message), '_ai_classify_message', return_value=True):
            result = self.test_message.action_ai_classify()

            self.assertEqual(result['type'], 'ir.actions.client')
            self.assertEqual(result['params']['type'], 'success')

    def test_ai_classify_attached_message(self):
        """Test that attached messages are not classified."""
        attached_message = self.env['mail.message'].create({
            'subject': 'Attached message',
            'body': '<p>Content</p>',
            'is_unattached': False,
        })

        result = attached_message._ai_classify_message()
        self.assertFalse(result)
