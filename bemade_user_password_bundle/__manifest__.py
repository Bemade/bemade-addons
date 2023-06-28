# -*- coding: utf-8 -*-
{
    'name': "User Password Bundle",

    'summary': """
        Module to create password bundles and provide access to them for admins of a newly created user.
    """,

    'description': """
        This module automate the creation of a password bundle for new users in Odoo 15 and changes the default admin 
        ownership of bundle to admin/setting group instead of the bundle creator.
    """,

    'author': "Bemade",
    'website': "https://www.bemade.org",
    'category': 'Technical',
    'version': '0.1',
    'license': 'AGPL-3',
    'depends': ['odoo_password_manager'],

    'data': [
    ],
    'demo': [
    ],
}
