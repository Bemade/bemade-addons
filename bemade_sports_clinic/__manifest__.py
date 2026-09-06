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
    'version': "19.0.1.40.1",
    'summary': 'Comprehensive sports medicine clinic management with portal access and activity tracking.',
    'description': """
Sports Clinic Management System

A comprehensive solution for managing sports medicine clinics, focusing on player health, injury tracking, team collaboration, and integrated activity management.

Key Features:
- User roles and access control for clinic staff, treatment professionals, and portal users
- Player management with contact information and team memberships
- Injury tracking with comprehensive documentation and workflow
- Team management with staff assignments and portal access
- Activity management with mail.activity integration
- Portal access for coaches and field therapists
- Security and privacy with layered architecture
- Data protection with anonymization and retention policies
- Full French Canadian localization support
- Integration with mail system and project tasks
- Clinic worklist for therapists and a self-service sign-in kiosk for patients

This module provides a complete sports medicine clinic management solution with robust portal access, activity tracking, and team collaboration features while maintaining strict security and data privacy controls.

Clinic sign-in kiosk (Law 25)
-----------------------------
Patients sign themselves in on an iPad at the clinic — no patient account, no
patient login. The iPad is a supervised web clip that loads ONE stable URL
(/clinic/kiosk) forever: on first load the server registers the device behind
a long-lived HttpOnly cookie, and an unbound device shows a 6-character
pairing code. The therapist types that code into the kiosk card of their
portal clinic page, which binds the device to that one clinic and its time
window (30 minutes before the start to 30 minutes after the end); the kiosk
switches to the sign-in form by itself — nobody touches the iPad. The form
asks for first name, last name and date of birth; the three are matched
server-side against the clinic's own roster only. What the kiosk does and
does not do:

- renders in French regardless of the browser language (English available as
  a per-visitor toggle), with the privacy policy an inline expandable section
  — no navigation, no off-domain link anywhere on the kiosk;
- shows no roster, no count, no autocomplete and no search; the answer to a
  sign-in is one generic welcome carrying no name;
- the date of birth is typed, never displayed back; nothing typed is echoed;
- the sign-in POST answers by redirect (PRG): reload or back can never
  resubmit; an idle kiosk returns to a clean start screen by itself;
- a successful sign-in only marks the patient Arrived on the clinic's
  worklist (source: kiosk); a sign-in that matches NO file is queued on the
  worklist as an « unregistered » row carrying only the typed first name,
  last name and date of birth — the player sees the same welcome screen —
  and the therapist resolves it in one click (link to an existing file,
  create the player from the typed data, or remove); unresolved rows are
  purged a few days after the clinic (setting, default 7 days);
- a name-only match (patient file without a date of birth) is flagged
  « to confirm » for the therapist;
- devices can be unpaired from the portal card and revoked from the backend;
  never-paired device rows are purged daily;
- pages are served with Cache-Control: no-store, no-cache, must-revalidate,
  Pragma: no-cache and X-Robots-Tag: noindex — and never touch web storage;
- server logs carry record ids only, never names or dates of birth;
- failed attempts are rate-limited per device (10 per minute, then a
  5-minute lockout) and device registration per IP.
    """,
    "category": "Services/Medical",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "mail",  # Required for mail.activity functionality
        "portal", 
        "contacts",
        "base_setup",  # For res.config.settings base view inheritance
        "phone_validation",  # For phone number formatting in patient contacts
        "account",  # Ensure account portal templates (e.g., portal_my_home_invoice) are available
        "sale_management",  # Sales app UI + sale.order workflow for timesheet-driven quotations
        "purchase",  # For therapist-side POs
        "hr_timesheet",  # Ensure our portal card override loads after core timesheet portal
        "data_recycle",  # Retention engine extended with the Law 25 anonymize action
    ],
    "external_dependencies": {
        "python": [
            "pytz",  # For timezone handling in injury tracking
        ],
    },
    "data": [
        "security/sports_clinic_groups.xml",
        "security/sports_clinic_portal_groups.xml",
        "security/ir.model.access.csv",
        "security/sports_clinic_rules.xml",
        "security/sports_clinic_portal_rules.xml",
        "security/mail_activity_portal_rules.xml",
        "security/sports_event_rules.xml",
        "security/partner_access.xml",
        "security/sports_event_timesheet_rules.xml",
        "security/team_digest_rules.xml",
        "security/sports_quick_note_rules.xml",
        "security/sports_clinic_attendance_rules.xml",
        # Task 1401: personal /my/teams order, own-rows-only rule.
        "security/sports_team_user_rank_rules.xml",
        "data/sports_clinic_data.xml",
        "data/material_report_data.xml",
        "data/admin_access_data.xml",
        # "data/project_portal_demo_data.xml",  # Temporarily disabled for clean upgrade
        "data/cron_actions.xml",
        "data/data_recycle_model.xml",
        # Must precede sports_team_views.xml: its header button resolves
        # %(action_team_player_removal)d at parse time.
        "views/team_player_removal_wizard_views.xml",
        "views/sports_team_views.xml",
        "views/sports_patient_injury_views.xml",
        "views/sports_clinic_menus.xml",
        # Task 1399: attendance report (pivot/graph/list) + the Reports menu.
        # After the menus (parent = sports_clinic_root), before the event views
        # (their smart-button action points at these views' model).
        "views/sports_clinic_attendance_views.xml",
        "views/team_digest_views.xml",
        "views/sports_patient_views.xml",
        # Task 1384: shared "Effacer"/Clear macro for long-text portal fields.
        # Load before the portal templates that t-call it.
        "views/portal_field_clear_templates.xml",
        # Task 1414: the portal patient combo snippet (typeahead over a real
        # <select>, « Last, First »). Load before every template that t-calls it.
        "views/portal_widgets_templates.xml",
        "views/sports_clinic_portal_views.xml",
        "views/team_digest_portal_templates.xml",
        "views/sports_patient_injury_portal.xml",
        "views/player_management_portal_templates.xml",
        "views/injury_management_portal_templates.xml",
        "views/injury_note_history_portal_templates.xml",
        "views/task_management_portal_templates.xml",
        "views/events_portal_templates.xml",
        "views/event_invoicing_wizard_views.xml",
        "views/event_batch_invoicing_wizard_views.xml",
        "views/event_vendor_po_wizard_views.xml",
        "views/purchase_order_views.xml",
        "views/event_recurrence_wizard_views.xml",
        "views/event_cancel_wizard_views.xml",
        "views/res_config_settings_views.xml",
        "views/sports_event_views.xml",
        "views/portal_activity_detail_template.xml",
        "views/portal_messages_template.xml",
        "views/portal_attachments_template.xml",
        "views/portal_event_detail_template.xml",
        "views/portal_event_edit_template.xml",
        "views/portal_event_create_template.xml",
        "views/portal_timesheets_templates.xml",
        "views/treatment_note_views.xml",
        "views/sports_quick_note_views.xml",
        "views/quick_note_portal_templates.xml",
        # Task 1398: the TP clinic worklist (/my/clinics, /my/clinic/<id>).
        "views/clinic_portal_templates.xml",
        # Task 1397/1433: the public clinic sign-in kiosk (stable
        # /clinic/kiosk dispatcher, device bound by pairing code).
        "views/clinic_kiosk_templates.xml",
        # Task 1433: backend admin for the kiosk devices (system only).
        "views/sports_clinic_kiosk_device_views.xml",
        # Task 1415: organization staff (line views, promotion wizard). Must
        # precede res_partner_views.xml: the org form's « Promote » button
        # resolves %(action_team_org_staff_promote)d at parse time.
        "views/sports_organization_staff_views.xml",
        # Task 1416: temporary (dated) staff access grants — list / form /
        # action + Admin menu; the team form's smart button and the org form's
        # list use them.
        "views/sports_staff_grant_views.xml",
        "views/res_partner_views.xml",
        "views/team_role_mass_assign_wizard_views.xml",
        "views/patient_merge_wizard_views.xml",
        "views/res_users_views.xml",
    ],
    "demo": [
        "data/demo/sports_clinic_demo_data.xml",
        "data/demo/sports_clinic_demo_extras.xml",
        "data/demo/sports_clinic_demo_products.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
    'post_init_hook': 'post_init_hook',
    "assets": {
        "web.assets_backend": [
            # Task 1272: single-column full-width team-dashboard digest kanban.
            "bemade_sports_clinic/static/src/scss/dashboard_kanban.scss",
            # Task 1272 (round 3): « voir plus »/« voir moins » de-dup — shared
            # with the portal so both surfaces toggle identically.
            "bemade_sports_clinic/static/src/scss/dashboard_digest.scss",
        ],
        "web.assets_frontend": [
            # Ensure legacy jQuery helpers exist where some website widgets expect them
            "bemade_sports_clinic/static/src/js/jquery_scrolling_polyfill.js",
            # Defensive patch for website TOC snippet to avoid null textContent errors
            "bemade_sports_clinic/static/src/js/website_toc_safety_patch.js",
            "bemade_sports_clinic/static/src/scss/portal_badges.scss",
            # Task 1272 (round 3): same digest « voir plus » de-dup on the portal.
            "bemade_sports_clinic/static/src/scss/dashboard_digest.scss",
            # Task 1385: homogenized portal card expandable styling + the
            # lazy-load toggle listener for the recent-changes feed.
            "bemade_sports_clinic/static/src/scss/portal_card.scss",
            "bemade_sports_clinic/static/src/js/portal_card_recent_changes.js",
            # Task 1389: lazy-loader for the team-dashboard digest-history modal.
            "bemade_sports_clinic/static/src/js/portal_digest_history.js",
            # Task 1384: one-tap "Effacer"/Clear for long-text portal fields.
            "bemade_sports_clinic/static/src/js/portal_field_clear.js",
            # Task 1398: desktop drag-reorder for the clinic worklist (plus its
            # small drag affordance styling). Progressive enhancement only — the
            # up/down buttons work without it. Task 1401: the same script/styles
            # drive the /my/teams personal order (data-reorder-* opt-in).
            "bemade_sports_clinic/static/src/scss/portal_clinic.scss",
            "bemade_sports_clinic/static/src/js/portal_clinic_reorder.js",
            # Task 1397: worklist auto-refresh (20 s poll of the fragment route
            # while the tab is visible) + the kiosk-link Copy button. Both are
            # progressive enhancement — reload / select-the-text work without.
            "bemade_sports_clinic/static/src/js/portal_clinic_worklist_refresh.js",
            # Task 1411: snap the dossier's match / practice selects to a valid
            # pair. Progressive enhancement — the server validates regardless.
            "bemade_sports_clinic/static/src/js/portal_clinic_quick_status.js",
            # Task 1412: the dossier's injury modal (quick-add / edit form
            # fragments fetched into #clinicInjuryModal). Progressive
            # enhancement — the same links open the full pages without it.
            "bemade_sports_clinic/static/src/js/portal_clinic_injury_modal.js",
            # Task 1413: « Cancel » of the inline treatment-note edit form
            # (clinic notes table + player notes tab). Progressive enhancement
            # — the <details> summary opens / closes the form without it.
            "bemade_sports_clinic/static/src/js/portal_treatment_note_edit.js",
            # Task 1414: portal patient combo — typeahead over the rendered
            # <select> options (clinic add-patient, quick-note pickers).
            # Progressive enhancement — the plain select posts without it.
            "bemade_sports_clinic/static/src/scss/portal_widgets.scss",
            "bemade_sports_clinic/static/src/js/portal_patient_combo.js",
        ],
        # Also load in lazy bundle since many website widgets initialize lazily
        "web.assets_frontend_lazy": [
            "bemade_sports_clinic/static/src/js/jquery_scrolling_polyfill.js",
            # Ensure patch is also present in lazy assets where snippet may initialize
            "bemade_sports_clinic/static/src/js/website_toc_safety_patch.js",
            # Task 1385: the card lazy-loader must also be present where portal
            # pages initialize via the lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_card_recent_changes.js",
            # Task 1389: digest-history modal loader also present in lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_digest_history.js",
            # Task 1384: clear control also present in lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_field_clear.js",
            # Task 1398: clinic worklist drag also present in lazy bundle.
            "bemade_sports_clinic/static/src/scss/portal_clinic.scss",
            "bemade_sports_clinic/static/src/js/portal_clinic_reorder.js",
            # Task 1397: worklist auto-refresh also present in lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_clinic_worklist_refresh.js",
            # Task 1411: quick status snap also present in lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_clinic_quick_status.js",
            # Task 1412: injury modal loader also present in lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_clinic_injury_modal.js",
            # Task 1413: note edit cancel also present in lazy bundle.
            "bemade_sports_clinic/static/src/js/portal_treatment_note_edit.js",
            # Task 1414: patient combo also present in lazy bundle.
            "bemade_sports_clinic/static/src/scss/portal_widgets.scss",
            "bemade_sports_clinic/static/src/js/portal_patient_combo.js",
        ],
    },
}
