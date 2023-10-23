
# -*- coding: utf-8 -*-
{
    'name': 'Bemade Sethy',
    'version': '1.0',
    'category': 'Specific Module Category',  # Specify your module's category here
    'summary': 'This module is developped by Bemade to instantiate the Sethy Odoo',  # Provide a brief summary of the module
    'author': 'Bemade',
    'website': 'https://bemade.org',
    'email': 'it@bemade.org',
    'license': 'GPL-3',
    'depends': [
        # List of module dependencies
        'base',
        'contact',
        'crm',
        'membership',
        'partner_multi_relation'
        'web_responsive'
    ],
    'data': [
        # Reference to XML, CSV, and other data files
        'data/company_data.xml',
    ],
    'demo': [
        # Reference to demo data files
    ],
    'installable': True,
    'auto_install': False,
    'application': False,  # Set to True if the module is an app
    'description': """
Main module for Fondation Séthy
==================================
This module install base componnent and will also setup default value according to the Fedation Séthy.

This will allow to put all the customisation here and add other module from Oca or our repos if needed.

Only code specific to Fondation Sethy reside in this module, the reusable stuff should be put in small deicatede module elsewhere
""",
}
