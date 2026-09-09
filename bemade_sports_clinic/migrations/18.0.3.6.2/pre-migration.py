"""Force re-application of clinic record rules.

Both sports_clinic_rules.xml and sports_clinic_portal_rules.xml are
wrapped in <data noupdate="1"> so that admins who tweak the rules in
the UI don't get overwritten on every module upgrade. Flipping
ir_model_data.noupdate to False does NOT actually convince Odoo's
XML loader to re-apply the rule — the loader honours the XML
`noupdate="1"` attribute on the parent <data> block independently.

Workaround: this pre-migration directly writes the desired
domain_force values into ir_rule via SQL. The values must stay in
sync with the XML in security/sports_clinic_rules.xml and
security/sports_clinic_portal_rules.xml. Whenever you add a new
domain to either, mirror it here so existing installs pick it up.
"""

import logging

_logger = logging.getLogger(__name__)

# Map of bemade_sports_clinic ir_model_data.name → desired domain_force.
# Mirrors the XML; if you change the XML, mirror it here too.
RULES_TO_FORCE = {
    'portal_medical_professional_patient_access':
        "[('team_ids.staff_ids.user_ids', 'in', user.id)]",
    'portal_medical_professional_injury_access':
        "[('patient_id.team_ids.staff_ids.user_ids', 'in', user.id)]",
    'portal_treatment_professional_player_access':
        "[('team_ids.staff_ids.user_ids', 'in', user.id)]",
    'portal_treatment_professional_team_access':
        "[('staff_ids.user_ids', 'in', user.id)]",
    'portal_coach_injury_access':
        "[('patient_id.team_ids.staff_ids.user_ids', 'in', user.id), "
        "('hidden_from_coaches', '=', False)]",
    'restrict_staff_access_to_team_injuries':
        "[('patient_id.team_ids.staff_ids.user_ids', 'in', user.id), "
        "('hidden_from_coaches', '=', False)]",
    'tp_internal_team_injury_full_access':
        "[('patient_id.team_ids.staff_ids.user_ids', 'in', user.id)]",
}


def migrate(cr, version):
    # Clear the noupdate flag too so future upgrades that change the XML
    # *do* take effect through the loader (in case Odoo's behaviour
    # tightens up to honour the field in a future version).
    names = list(RULES_TO_FORCE.keys())
    cr.execute(
        """
        UPDATE ir_model_data
           SET noupdate = false
         WHERE module = 'bemade_sports_clinic'
           AND model = 'ir.rule'
           AND name = ANY(%s)
        """,
        (names,),
    )

    # Resolve XML IDs to ir_rule row IDs.
    cr.execute(
        """
        SELECT name, res_id
          FROM ir_model_data
         WHERE module = 'bemade_sports_clinic'
           AND model = 'ir.rule'
           AND name = ANY(%s)
        """,
        (names,),
    )
    name_to_res_id = dict(cr.fetchall())
    if not name_to_res_id:
        _logger.info("No clinic rule records to force-update.")
        return

    updated = 0
    for name, domain in RULES_TO_FORCE.items():
        res_id = name_to_res_id.get(name)
        if not res_id:
            continue
        cr.execute(
            "UPDATE ir_rule SET domain_force = %s WHERE id = %s",
            (domain, res_id),
        )
        updated += cr.rowcount
    _logger.info("Force-updated domain_force on %d clinic ir.rule records.", updated)
