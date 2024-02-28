# -*- coding: utf-8 -*-
{
    "name": "Time Off Alternative Follower",
    "version": "17.0.0.0.1",
    "category": "Extra Tools",
    'summary': 'Add Alternative Follower When Receiving Message While On Time Off',
    "description": """
        Add Alternative Follower When Receiving Message While On Time Off
    """,
    "author": "Bemade",
    'website': 'https://www.bemade.org',
    "depends": [
        'hr_holidays',
        'mail'
    ],
    "data": [
        'views/hr_leave_views.xml',
    ],
    "auto_install": False,
    "installable": True,
    'license': 'OPL-1'
}
