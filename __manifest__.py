{
    'name': 'Durpro Field Service Management',
    'version': '15.0.1.0.0',
    'summary': 'Adds functionality necessary for managing field service operations at Durpro.',
    'description': 'Adds functionality necessary for managing field service operations at Durpro.',
    'category': 'Services/Field Service',
    'author': 'Bemade Inc.',
    'website': 'http://www.bemade.org',
    'license': 'LGPL-3',
    'depends': ['project', 'stock', 'sale', 'sale_project', 'sale_stock'],
    'data': ['views/task_template_views.xml',
             'security/ir.model.access.csv',
             'views/product_views.xml',
             ],
    'assets': {
        'web.assets_tests': [
            'durpro_fsm/static/tests/tours/task_template_tour.js',
        ],
    },
    'installable': True,
    'auto_install': False
}
