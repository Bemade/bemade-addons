#
#    Bemade Inc.
#
#    Copyright (C) October 2023 Bemade Inc. (<https://www.bemade.org>).
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
    'name': 'Sports Clinic Management',
    'version': '17.0.1.5.2',
    'summary': 'Manage the patients of a sports medicine clinic.',
    'description': """
        Adds the notion of sports teams, players (patients), coaches and treatment
        professionals. The core purpose of this module is to keep track of the treatment
        history of players and to make it appropriately accessible to the various
        involved parties (medical practitioners, clinic staff, team staff, and patients).

        Internal users get access to patient data as appropriate, i.e.
        treatment professionals get full access to their own patients' data, clinic
        staff users get access to basic patient data needed for contacting patients, etc.

        External users (portal users) can be added to give coaches and other team
        personnel access to limited player data such as estimated return-to-play dates.
    """,
    'category': 'Services/Medical',
    'author': 'Bemade Inc.',
    'website': 'https://www.bemade.org',
    'license': 'OPL-1',
    'depends': ['portal', 'contacts'],
    'data': [
        'security/sports_clinic_groups.xml',
        'security/ir.model.access.csv',
        'security/sports_clinic_rules.xml',
        'data/sports_clinic_data.xml',
        'views/sports_team_views.xml',
        'views/sports_clinic_menus.xml',
        'views/sports_patient_injury_views.xml',
        'views/sports_patient_views.xml',
        'views/sports_clinic_portal_views.xml',
        'views/res_partner_views.xml',
    ],
    'demo': ['data/demo/sports_clinic_demo_data.xml'],
    'installable': True,
    'auto_install': False,
    'application': True,
}
