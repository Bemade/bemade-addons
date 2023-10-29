
# -*- coding: utf-8 -*-
{
    'name': 'Bemade Sethy',
    'version': '1.0',
    'category': 'Specific Module Category',  # Specify your module's category here
    'summary': 'This module is developed by Bemade to instantiate the Sethy Odoo',  # Provide a brief summary of the module
    'author': 'Bemade',
    'website': 'https://bemade.org',
    'email': 'it@bemade.org',
    'license': 'GPL-3',
    'depends': [
        # List of module dependencies
        'base',
        'contacts',
        'crm',
        'membership',
        'partner_multi_relation'
    ],
    'data': [
        # Reference to XML, CSV, and other data files
        'data/company_data.xml',
        'data/partner_tags_data.xml',
        'data/partner_relations_data.xml',
        'views/res_partner_views.xml',
        'views/res_partner_relation_views.xml',
        'views/membership_membership_line.xml'

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
This module installs base components and will also set up default values according to the Fondation Séthy.

This will allow us to put all the customization here and add other modules from Oca or our repos if needed.

Only code specific to Fondation Sethy resides in this module, the reusable stuff should be put in other small dedicated modules elsewhere
""",
}
