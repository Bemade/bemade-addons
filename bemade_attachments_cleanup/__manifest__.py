{
    'name': "Attachment Cleanup",
    'version': '1.0.1',
    'author': "Bemade",
    'website': "http://www.bemade.org",
    'category': 'Tools',
    'license': 'OPL-1',
    'summary': "Find and delete missing attachments",
    'description': """
    This module adds a wizard in the settings menu to find and delete missing attachments.
    The wizard lists all attachments that are not found in the filestore, and allows the user to select and delete them.
    Please use this tool with caution, as deleting attachments cannot be undone.
    """,
    'depends': ['base'],
    'data': [
        'wizard/attachment_cleanup_wizard_view.xml',
        'security/ir.model.access.csv',

    ],
    'installable': True,
    'application': False,
}
