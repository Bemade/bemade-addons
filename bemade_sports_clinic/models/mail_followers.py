from odoo import models, fields, api, _


class MailFollowers(models.Model):
    _inherit = "mail.followers"

    # This is a user quality of life modification, to avoid duplicated message subtype subscription for internal
    # and external notifications (since both subtypes are default=True).

    def write(self, vals):
        super().write(vals)
        subtypes_map = self.__subtypes_map()
        if self.res_model in subtypes_map and 'subtype_ids' in vals:
            internal_subtype, external_subtype = subtypes_map.get(self.res_model)
            if external_subtype in self.subtype_ids and internal_subtype in self.subtype_ids:
                self.subtype_ids = self.subtype_ids - external_subtype

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        subtypes_map = self.__subtypes_map()
        to_fix = {
            model:
                recs.filtered(
                    lambda rec: rec.res_model == model
                                and subtypes[0] in rec.subtype_ids
                                and subtypes[1] in rec.subtype_ids
                ) for model, subtypes in subtypes_map.items()
        }
        for model, records in to_fix.items():
            for rec in records:
                rec.subtype_ids = rec.subtype_ids - subtypes_map[model][1]
        return recs

    def __subtypes_map(self):
        xml_id_fmt_string = "bemade_sports_clinic.subtype_{0}_{1}_update"
        return {
            'sports.patient': (
                self.env.ref(xml_id_fmt_string.format('patient', 'internal')),
                self.env.ref(xml_id_fmt_string.format('patient', 'external')),
            ),
            'sports.patient.injury': (
                self.env.ref(xml_id_fmt_string.format('patient_injury', 'internal')),
                self.env.ref(xml_id_fmt_string.format('patient_injury', 'external')),
            ),
        }
