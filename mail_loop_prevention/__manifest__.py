# Copyright 2025 DurPro
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Mail Loop Prevention",
    "summary": "Prevent auto-reply communication loops between mail servers",
    "version": "18.0.2.0.0",
    "license": "LGPL-3",
    "author": "Bemade Inc",
    "website": "https://github.com/durpro/durpro",
    "depends": ["mail"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}
