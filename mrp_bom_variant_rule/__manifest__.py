#
#    Bemade Inc.
#
#    Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    License: LGPL-3
#
{
    "name": "BOM generation from variant attribute rules",
    "version": "19.0.1.2.1",
    "summary": "Generate a variant's bill of materials on demand from attribute-driven rules",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "category": "Manufacturing/Manufacturing",
    "license": "LGPL-3",
    "depends": [
        "mrp",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/mrp_bom_rule_set_views.xml",
        "views/mrp_bom_rule_views.xml",
        "views/product_attribute_views.xml",
        "views/mrp_bom_views.xml",
        "views/product_views.xml",
        "views/mrp_menus.xml",
        "views/res_config_settings_views.xml",
    ],
    "demo": [],
    "installable": True,
    "auto_install": False,
}
