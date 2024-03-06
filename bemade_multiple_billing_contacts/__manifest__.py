#
#    Bemade Inc.
#
#    Copyright (C) June 2023 Bemade Inc. (<https://www.bemade.org>).
#    Author: mdurepos (Contact : it@bemade.org)
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
{
    'name': 'Multiple Billing Contacts',
    'version': '17.0.1.0.1',
    'summary': 'Send invoices to multiple contacts by default.',
    'description': """
        By default, newly created invoices add all invoice addresses for the given partner as
        followers on the invoice. If billing contacts are set manually on the sales order, those billing
        contacts are added as followers on the invoice instead.
    """,
    'category': 'Invoicing Management',
    'author': 'Bemade Inc.',
    'website': 'https://www.bemade.org',
    'license': 'OPL-1',
    'depends': [
        'sale',
        'account',
        'bemade_partner_root_ancestor',
    ],
    'data': [
        'views/account_move_views.xml',
        'views/res_partner_views.xml'
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
}
