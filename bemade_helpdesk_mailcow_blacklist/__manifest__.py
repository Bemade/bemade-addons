# -*- coding: utf-8 -*-
{
    'name': 'Helpdesk Mailcow Blacklist',
    'version': '1.0.0',
    'category': 'Administration',
    'summary': 'Module for adding blacklist functionality to the helpdesk.',
    'description': """
    Helpdesk Mailcow Blacklist

    This module extends the functionality of the Helpdesk and Mailcow Blacklist modules by adding an action to blacklist the sender of a Helpdesk ticket. 

    Main Features:
    - Adds a button on Helpdesk tickets to blacklist the email sender.
    - This button is only visible when an email is associated with the ticket.
    - Blacklisting an email sender automatically moves the Helpdesk ticket to a new 'Spam' stage, which is marked as closed.
    - The 'Spam' stage is automatically created by this module.
    """,
    'sequence': 10,
    'license': 'GPL-3',
    'author': 'Bemade',
    'website': 'https://www.bemade.org',
    'depends': [
        'helpdesk',
        'bemade_mailcow_integration'
    ],
    'data': [
        # 'security/ir.model.access.csv',
        'data/helpdesk_stages.xml',
        'views/helpdesk_ticket_views.xml',
    ],
    'demo': [
        'demo/demo.xml'
    ],
    'installable': True,
    'application': False,
    'auto_install': False
}
