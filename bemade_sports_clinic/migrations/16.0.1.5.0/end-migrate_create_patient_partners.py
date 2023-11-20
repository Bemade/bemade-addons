from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    patients = env['sports.patient'].search([('partner_id', '=', False)])
    for patient in patients:
        partner = env['res.partner'].create({
            'name': patient._get_name_from_first_and_last(patient.first_name, patient.last_name)
        })
        patient.partner_id = partner