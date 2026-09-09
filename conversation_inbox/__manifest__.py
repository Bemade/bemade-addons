#
#    Bemade Inc.
#
#    Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact: marc@bemade.org)
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
    "name": "Conversation Inbox",
    "version": "18.0.2.2.1",
    "category": "Discuss",
    "summary": "In-Odoo GTD inbox/triage viewer for browsable conversation "
    "transports (ingest-on-action, not an email client).",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "conversation_base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/conversation_inbox_capture_wizard_views.xml",
        "wizards/conversation_inbox_reassign_wizard_views.xml",
        "wizards/conversation_inbox_reply_wizard_views.xml",
        "views/conversation_inbox_views.xml",
        "views/conversation_transport_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "conversation_inbox/static/src/inbox/**/*",
        ],
        # Tours ship in the test bundle only -- they are a regression
        # guard, not a feature, and have no business in a client's
        # backend assets.
        "web.assets_tests": [
            "conversation_inbox/static/tests/tours/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
