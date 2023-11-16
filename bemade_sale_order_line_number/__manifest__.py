{
    'name': 'Sale Order Line Sequence View Modification',
    'version': '1.0',
    'summary': 'Modifies the Sale Order Line View to show Sequence twice',
    'sequence': 10,
    'description': """
        This module modifies the Sale Order Line view to display the sequence field as both a handle widget and a number.
        """,
    'category': 'Sales Management',
    'author': 'Bemade',
    'website': 'https://www.bemade.org',
    'depends': ['sale_management'],
    'data': [
        'views/sale_order_view.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}