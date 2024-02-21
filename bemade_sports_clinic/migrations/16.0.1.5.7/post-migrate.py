from odoo import api, SUPERUSER_ID, Command


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    patient_followers = env['mail.followers'].search([('res_model', '=',
                                                       'sports.patient')])
    injury_followers = env['mail.followers'].search([('res_model', '=',
                                                      'sports.patient.injury')])
    for f in patient_followers:
        if f.partner_id.user_ids.has_group('base.group_user'):
            subtype = env.ref('bemade_sports_clinic.subtype_patient_internal_update').id
        else:
            subtype = env.ref('bemade_sports_clinic.subtype_patient_external_update').id
        f.write({'subtype_ids': [Command.link(subtype)]})
    for f in injury_followers:
        if f.partner_id.user_ids.has_group('base.group_user'):
            subtype = env.ref('bemade_sports_clinic.subtype_patient_injury_internal_update').id
        else:
            subtype = env.ref('bemade_sports_clinic.subtype_patient_injury_external_update').id
        f.write({'subtype_ids': [Command.link(subtype)]})
