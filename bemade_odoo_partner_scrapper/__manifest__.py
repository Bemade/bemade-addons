# -*- coding: utf-8 -*-
{
    'name': 'Bemade Odoo Partner Scrapper',
    'version': '17.0.0.0.0',
    'category': 'Administration',
    'summary': 'Module for scraping partners from odoo.com.',
    'description': """
    This module enables the scraping of partners from odoo.com. It allows for the collection and management of partner contact information.

    Main Features:
    * Automatically scrape partners from odoo.com.
    * Extracts partner name, website, and contact information.
    * Manage contact information of partners.
    """,
    'sequence': 10,
    'license': 'GPL-3',
    'author': 'Bemade',
    'website': 'https://www.bemade.org',
    'depends': ['base', 'contacts', 'sale_management', 'sale' , 'partner_multi_relation'],
    'data': [
        # No security
        'views/res_partner_views.xml',
        # Commented for migration to 17, raises error on update
        'data/res_partner_relation_type.xml'
    ],
    # "assets": {
    #     "web.assets_backend": [
    #         "bemade_odoo_partner_scrapper/static/src/js/odoo_scrapper.js",
    #         "bemade_odoo_partner_scrapper/static/src/xml/odoo_scrapper_templates.xml",
    #     ],
    # },
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False
}
