######################################################################################
#
#    Bemade Inc.
#
#    Copyright (C) 2023-June Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : mdurepos@durpro.com)
#
#    This program is under the terms of the Odoo Proprietary License v1.0 (OPL-1)
#    It is forbidden to publish, distribute, sublicense, or sell copies of the Software
#    or modified copies of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#
########################################################################################
{
    "name": "Improved Field Service Management",
    "version": "18.0.0.4.5",
    "summary": (
        "Adds functionality necessary for managing field service operations at Durpro."
    ),
    "category": "Services/Field Service",
    "author": "Bemade Inc.",
    "website": "http://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "sale_stock",
        "sale_project",
        "account",
        "project_enterprise",
        "industry_fsm",
        "industry_fsm_stock",
        "industry_fsm_report",
        "industry_fsm_sale_report",
        "fsm_equipment",
        "recursive_list_view",
        "bemade_partner_root_ancestor",
        "mail",
    ],
    "data": [
        "data/fsm_data.xml",
        "views/task_template_views.xml",
        "security/ir.model.access.csv",
        "views/product_views.xml",
        "views/res_partner.xml",
        "views/menus.xml",
        "views/task_views.xml",
        "views/fsm_visit_views.xml",
        "views/sale_order_views.xml",
        "reports/worksheet_custom_report_templates.xml",
        "reports/worksheet_custom_reports.xml",
        "wizard/new_task_from_template.xml",
        "wizard/res_config_settings.xml",
    ],
    "assets": {
        "web.report_assets_common": ["bemade_fsm/static/src/scss/bemade_fsm.scss"],
        "web.assets_backend": [
            # OWL list view extension for Project Tasks
            "bemade_fsm/static/src/views/project_task_list_view.js",
            # Ensure buttons template is available in the backend bundle
            "bemade_fsm/static/src/xml/project_task_list_buttons.xml",
        ],
        "web.assets_qweb": [
            "bemade_fsm/static/src/xml/project_view_buttons.xml",
            "bemade_fsm/static/src/xml/project_task_list_buttons.xml",
        ],
        # JS tour for the visit "Full Task Tree" recursive list (task 3360),
        # loaded only into the test bundle.
        "web.assets_tests": [
            "bemade_fsm/static/tests/tours/**/*",
        ],
    },
    "installable": True,
    "auto_install": False,
}
