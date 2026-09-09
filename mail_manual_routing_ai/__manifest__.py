# -*- coding: utf-8 -*-
{
    "name": "Lost Messages Routing - AI Improvements",
    "version": "18.0.1.0.0",
    "category": "Discuss",
    "summary": "AI-powered classification of lost messages using OpenWebUI",
    "description": """
AI-powered enhancements for lost message classification:

1. **Automatic Classification**: Uses OpenWebUI LLM to classify messages into subcategories
2. **Confidence Score**: Shows AI confidence level for each classification
3. **Configurable**: Set your OpenWebUI server URL and model
4. **Smart Routing**: Auto-categorize messages based on content analysis
    """,
    "author": "Bemade Inc.",
    "website": "https://bemade.org",
    "license": "LGPL-3",
    "depends": [
        "mail_manual_routing",
        "mail_manual_routing_ux",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/config_data.xml",
        "views/res_config_settings_views.xml",
        "views/mail_message_views.xml",
    ],
    "external_dependencies": {
        "python": ["requests"],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
