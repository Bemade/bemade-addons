{
    'name': 'Account Credit Hold',
    'version': '17.0.1.0.0',
    'summary': 'Allows setting clients on credit hold, blocking the ability confirm a new sales order.',
    'description': 'Allows setting clients on hold, blocking the ability confirm a new sales order.',
    'category': 'Accounting/Accounting',
    'author': 'Bemade Inc.',
    'maintainer': 'Marc Durepos <marc@bemade.org>',
    'website': 'http://www.bemade.org',
    'license': 'LGPL-3',
    'depends': ['sale', 'account_followup', 'stock'],
    'data': [
        'views/account_followup_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'views/stock_picking_views.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False
}
