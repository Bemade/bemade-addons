"""Clear noupdate=True on the four sports_clinic_data mail.template records.

Originally these templates lived inside <data noupdate="1"> in
sports_clinic_data.xml, so their ir_model_data rows were stamped with
noupdate=True. Moving the XML out of the noupdate block does NOT reset
that flag — Odoo respects the originally-stamped value forever, so
body_html / subject corrections never propagate on -u.

This pre-migration flips the flag once so the regular data load that
follows during this -u actually writes the new template body.
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_model_data
        SET noupdate = false
        WHERE module = 'bemade_sports_clinic'
          AND model = 'mail.template'
          AND name IN (
              'mail_template_patient_status_update',
              'mail_template_patient_new_internal_note',
              'mail_template_patient_injury_status_update',
              'mail_template_patient_injury_new_internal_note'
          )
        """
    )
