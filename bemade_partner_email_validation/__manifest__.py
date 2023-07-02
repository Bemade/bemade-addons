{
  'name': 'Validate Partner Email',
  'version': '1.0.0',
  'category': 'Extra Tools',
  'summary': 'Module to validate the email addresses of partners.',
  'description': """
  Validate Partner Email
  ===================

  This module adds a functionality to validate the email addresses of partners in Odoo. A new boolean field 'email_validated' is added to the 'res.partner' model. When an email address is entered or changed, 'email_validated' is set to False and a validation email is sent to the new email address. If the recipient clicks the link in the validation email, 'email_validated' is set to True. Before sending an email to a partner, the system checks whether the partner's email is validated and if not, a message is posted in the chatter.

  Main Features:
  --------------
  * Add 'email_validated' field to 'res.partner'.
  * Send validation email when 'email_validated' is False.
  * Post message in chatter when trying to send email to partner with unvalidated email.
  """,
  'sequence': 10,
  'license': 'GPL-3',
  'author': 'Bemade',
  'website': 'https://www.bemade.org',
  'depends': ['base', 'mail'],
  'data': [
  'security/ir.model.access.csv',
  'views/res_partner_views.xml',
  'data/mail_template_data.xml'
  ],
  'demo': ['demo/res_partner_demo.xml'],
  'installable': True,
  'application': False,
  'auto_install': False
}