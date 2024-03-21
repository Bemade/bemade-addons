{
    'name': 'Bemade Search Supplier Code',
    'version': '17.0.1.0.1',
    'summary': 'Search for products by supplier code',
    'sequence': 10,
    'description': """
        This module adds the ability to search for products by supplier code.
        """,
    'category': 'Inventory/Purchase',
    'author': 'Bemade',
    'website': 'https://www.bemade.org',
    'depends': [
        'purchase',
        'product'
    ],
    'data': [
        'views/product_product_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
