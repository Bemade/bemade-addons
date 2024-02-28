{
    'name': 'Automated Partner Association by Email Domain',
    'version': '17.0.0.0.0',
    'category': 'Extra Tools',
    'summary': 'Automatically associates partners with companies using matching email domains',
    'description': """
        This advanced utility module empowers Odoo users with the capacity to automate partner-company associations 
        based directly on email domains. It helps in eliminating manual effort by establishing a rule of correlation 
        between the email domain of a partner and the corresponding division or a company.

        The automation proceeds as follows:

        - On creation of partner records, the system will cross-verify the email domain against the companies 
        in the records.
        - If a match is detected, the partner will automatically be linked with that company.

        This module also takes care of instances where there are multiple companies with the same email domain. 
        In such cases, an email is dispatched to the partner with a selection interface to finalize the association.

        The module is a significant productivity enhancer for businesses that deal with a high number of partners 
        and require efficient management.
    """,
    'depends': [
        'base',
        'mail',
        'website'
    ],
    'data': [
        'views/res_partner_views.xml',
        'data/mail_template_data.xml',
        'data/template_data.xml'
    ],
    'license': 'AGPL-3',
    'author': 'Bemade',
    'website': 'https://bemade.org/',
    'installable': True,
    'auto_install': False
}
