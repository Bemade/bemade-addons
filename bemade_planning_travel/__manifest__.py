#
#    Bemade Inc.
#
#    Copyright (C) July 2023 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
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
    'name': 'Planning Travel Time',
    'version': '15.0.1.0.0',
    'summary': "Plan travel time for services planned via Odoo's Planning module.",
    'description': """ 
        Adds the ability to add travel planning records to existing planning records 
        linked to sale order lines. Travel planning records book time in the scheduled 
        resource's calendar. Travel distance is based on the resource's work address, if 
        available. Otherwise, travel is assumed to be between the client location and 
        the company's address.""",
    'category': 'Services/Field Service',
    'author': 'Bemade Inc.',
    'website': 'https://www.bemade.org',
    'license': 'OPL-1',
    'depends': ['sale_planning',
                'industry_fsm',
                'bemade_geo_routing'],
    'data': [''],
    'demo': [''],
    'installable': True,
    'auto_install': False,
}
