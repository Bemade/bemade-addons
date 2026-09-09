#
#    Bemade Inc.
#
#    Copyright (C) 2023-June Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License,
#    version 3.
#
#    For full license details, see https://www.gnu.org/licenses/lgpl-3.0.en.html.
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
    "name": "FSM Visit Confirmation",
    "version": "18.0.0.1.1",
    "summary": "Enable client feedback workflow for field service tasks",
    "description": """
        This module enhances the field service management workflow by leveraging Odoo's
        built-in rating system for client task confirmations. Key features include:

        * Automated rating requests to work order contacts when tasks reach specific stages
        * Configurable stages with rating email templates
        * Client-facing rating interface with direct links in emails
        * Support for task approval or change requests through ratings
        * Integration with existing work order contacts from bemade_fsm
        * Automatic task state updates based on client feedback
        * Real-time feedback through website messages and notifications
        * Chatter integration for client comments

        The module helps streamline communication between field service teams and clients
        by providing a clear feedback workflow and maintaining a record of all client
        interactions and approvals through Odoo's rating system.
    """,
    "category": "Services/Field Service",
    "author": "Bemade Inc.",
    "website": "http://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["industry_fsm", "bemade_fsm", "rating", "http_routing"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/mail_templates.xml",
        "views/project_task_views.xml",
        "views/fsm_task_client_requirement_views.xml",
        "views/project_portal_project_task_templates.xml",
        "views/project_task_type_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
