{
    'name': 'MSG to Mail Message',
    'version': '18.0.1.1',
    'category': 'Mail',
    'summary': 'Process MSG files as incoming emails',
    'license': 'LGPL-3',
    'description': """
        This module processes Outlook files (.msg) as incoming emails in Odoo when upload as attachments.

        Features
        ========
        1. Automatic MSG File Detection
           - Identifies .msg files by extension or MIME type
           - Automatic processing upon upload

        2. Message Content Extraction
           - Email subject
           - Message body
           - Sender information
           - Send date
           - Attachments

        3. Odoo Message Creation
           - Creates a mail.message in the chatter
           - Preserves all original email information
           - Integrates the message into existing discussion thread
           - Don't add email receipent as follower, just add message and attachments

        4. Attachment Management
           - Automatically extracts all attachments from MSG file
           - Creates standard Odoo attachments for each file
           - Links attachments to the created message
           - Preserves original filenames

        Usage
        =====
        - Simply upload a .msg file to Odoo
        - The module automatically processes the file
        - Message appears in the discussion thread
        - Attachments are accessible as standard attachments

        Technical Notes
        ===============
        Requires Python library 'extract-msg' for MSG file processing.
    """,
    'author': 'Bemade inc.',
    'website': 'https://www.bemade.org',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'external_dependencies': {
        'python': [
            'chardet',
            'extract-msg',
            'PyPDF2',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}