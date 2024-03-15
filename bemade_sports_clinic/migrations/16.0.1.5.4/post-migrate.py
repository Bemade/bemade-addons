from odoo import api, SUPERUSER_ID, Command

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    patient_followers = env['mail.followers'].search([('res_model', '=',
                                                       'sports.patient')])
    injury_followers = env['mail.followers'].search([('res_model', '=',
                                                      'sports.patient.injury')])
    for f in patient_followers:
        f.write(
            {
                'subtype_ids':
                    [Command.link(env.ref('bemade_sports_clinic.subtype_patient_update').id)]
            }
        )
    for f in injury_followers:
        f.write(
            {
                'subtype_ids':
                    [Command.link(env.ref('bemade_sports_clinic.subtype_patient_injury_update').id)]
            })
