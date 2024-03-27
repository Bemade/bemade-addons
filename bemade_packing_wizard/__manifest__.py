{
    'name': 'Packing wizard',
    'version': '17.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Allow automated packing type creation',
    'description': """
        This module allows users simply enter all the package dimensions on every packing and it will create the packing 
        type automatically if it not exists, use it the create the package with the weight and related package type.

        You need to activate the auto create package feature on the delivery carrier to use this feature.
    """,
    'depends': [
        'stock_delivery'
    ],
    'data': [
        'views/stock_package_views.xml',
        'views/delivery_carrier_views.xml',
        'wizard/choose_delivery_package_views.xml',
    ],
    'license': 'AGPL-3',
    'author': 'Bemade',
    'website': 'https://bemade.org/',
    'installable': True,
    'auto_install': False
}
