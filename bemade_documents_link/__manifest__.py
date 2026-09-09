{
    "name": "Documents - Link Existing",
    "version": "18.0.2.0.0",
    "summary": "Link an existing Documents record (incl. spreadsheets) to any "
               "number of mail.thread records, from either side.",
    "category": "Productivity/Documents",
    "author": "Bemade Inc.",
    "maintainer": "Marc Durepos <marc@bemade.org>",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["documents"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/documents_link_wizard_views.xml",
        "data/ir_actions_server_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bemade_documents_link/static/src/link_document_cog_menu/*.js",
            "bemade_documents_link/static/src/link_document_cog_menu/*.xml",
            "bemade_documents_link/static/src/link_to_record/*.js",
            "bemade_documents_link/static/src/link_to_record/*.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
}
