#
#    Bemade Inc.
#
#    Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    License: LGPL-3
#
{
    "name": "BOM generation from variant attribute rules - PLM",
    "version": "18.0.1.0.0",
    "summary": "Route generated BOM revisions through an engineering change order",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "category": "Manufacturing/Product Lifecycle Management (PLM)",
    "license": "LGPL-3",
    "depends": [
        "mrp_bom_variant_rule",
        "mrp_plm",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "auto_install": True,
}
