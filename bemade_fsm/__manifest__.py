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
    'name': 'Improved Field Service Management',
    'version': '17.0.0.1.0',
    'summary': 'Adds functionality necessary for managing field service operations at Durpro.',
    'description': 'Adds functionality necessary for managing field service operations at Durpro.',
    'category': 'Services/Field Service',
    'author': 'Bemade Inc.',
    'website': 'http://www.bemade.org',
    'license': 'OPL-1',
    'depends': [
        'project_enterprise',
        'project_forecast',
        'stock',
        'sale',
        'sale_project',
        'sale_stock',
        'sale_planning',
        'worksheet',
        'industry_fsm_stock',
        'industry_fsm_report',
        'industry_fsm_sale_report',
        'bemade_partner_root_ancestor',
        'mail',
    ],
    'data': [
        'data/fsm_data.xml',
        'views/task_template_views.xml',
        'views/equipment.xml',
        'security/ir.model.access.csv',
        'views/product_views.xml',
        'views/res_partner.xml',
        'views/menus.xml',
        'views/task_views.xml',
        'views/sale_order_views.xml',
        'reports/worksheet_custom_report_templates.xml',
        'reports/worksheet_custom_reports.xml',
        'wizard/new_task_from_template.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'bemade_fsm/static/src/scss/bemade_fsm.scss'
        ],
        'web.assets_backend': [
            #  BV: need to readd these files
            # 'bemade_fsm/static/src/js/kanban_view.js',
            # 'bemade_fsm/static/src/js/list_view.js',
        ],
        'web.assets_qweb': [
            'bemade_fsm/static/src/xml/project_view_buttons.xml',
        ]
    },
    'installable': True,
    'auto_install': False
}
