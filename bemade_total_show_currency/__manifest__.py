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
    'name': 'Show Currency in total',
    'version': '17.0.0.0.1',
    'summary': 'Show Currency in total',
    'description': """
        This module adds the ability to view currency in total in all pdf.
    """,
    'category': 'Account',
    'author': 'Bemade Inc.',
    'website': 'https://www.bemade.org',
    'license': 'OPL-1',
    'depends': [
        'sale',
        'purchase',
        'account'
    ],
    'data': [
        'views/total_template.xml'
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
}
