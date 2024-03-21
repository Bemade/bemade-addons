{
    'name': 'Module Linker',
    'version': '17.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Link modules from external repositories',
    'description': """
        This module allows users to link modules from external repositories.
    """,
    'depends': [
        'base',
        'base_setup'
    ],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'license': 'AGPL-3',
    'author': 'Bemade',
    'website': 'https://bemade.org/',
    'installable': True,
    'auto_install': False,
    'hooks': [
        'post_init_hook',
    ],
}
