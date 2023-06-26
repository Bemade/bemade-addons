# -*- coding: utf-8 -*-
{
    'name': 'User Custom App Order',
    'version': '1.0.1',
    'license': 'GPL-3',
    'author': 'Bemade',
    'website': 'http://www.bemade.org',
    'category': 'Extra Tools',
    'summary': 'Allows users to customize the order of apps in the app switcher',
    'description': """
User Custom App Order
=====================
This module allows each user to customize the order of their apps in the app switcher in Odoo.

Features:
---------
* Users can choose the order of their apps in the app switcher.
* Users can only modify their own app order. Administrators can modify the order for any user.
* The module also automatically handles the creation of app order records for new users and new apps.

Installation:
-------------
No specific steps required for the installation.

Configuration:
--------------
No specific configuration required for this module.
    """,
    'depends': ['hr',],
    'data': [
        'security/ir.model.access.csv',
        'views/user_menu_sequence.xml',
        'views/res_users_view.xml'
    ],
    'assets': {
        'web.assets_tests': ['bemade_user_custom_apps_order/static/tests/tours/custom_app_order_tour.js'],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
