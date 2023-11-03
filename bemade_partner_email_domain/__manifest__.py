{
    'name': 'Partner Email Domain Auto-Set',
    'version': '15.0.0.0.0',
    'category': 'Extra Tools',
    'summary': 'Allow to autolink partner based on email domain',
    'description': """
        This module allows users to automatically link a partner to a company based on the email domain.
    """,
    'depends': [
        'base',
        'mail'
    ],
    'data': [
        'views/res_partner_views.xml',
        'data/mail_template.xml'
    ],
    'license': 'AGPL-3',
    'author': 'Bemade',
    'website': 'https://bemade.org/',
    'installable': True,
    'auto_install': False
}
