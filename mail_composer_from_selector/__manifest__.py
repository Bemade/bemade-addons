# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Mail Composer From Address Selector",
    "summary": "Allow users to select from authorized email addresses when composing emails",
    "version": "18.0.1.0.0",
    "category": "Social",
    "author": "Bemade Inc. (Marc Durepos <marc@bemade.org>)",
    "license": "LGPL-3",
    "depends": [
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/mail_from_address_views.xml",
        "views/res_users_views.xml",
        "views/mail_compose_message_views.xml",
    ],
    "installable": True,
    "application": False,
}