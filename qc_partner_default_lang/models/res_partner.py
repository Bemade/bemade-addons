from odoo import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _fr_ca_installed(self):
        return self.env['res.lang'].search_count([('code', '=', 'fr_CA'), ('active', '=', True)]) > 0

    @api.model_create_multi
    def create(self, vals_list):
        fr_ca_ok = self._fr_ca_installed()
        for vals in vals_list:
            # Only set language if it's not already specified
            if not vals.get('lang'):
                state = vals.get('state_id')
                if state and fr_ca_ok:
                    state_rec = self.env['res.country.state'].browse(state)
                    # Check if the state is Quebec
                    if state_rec.code == 'QC' and state_rec.country_id.code == 'CA':
                        vals['lang'] = 'fr_CA'

        return super().create(vals_list)

    @api.onchange('state_id', 'country_id')
    def _onchange_location_set_lang(self):
        # Only suggest language change if it's a new record (id not set yet)
        if not self.id and not self.lang:
            if self.state_id and self.state_id.code == 'QC' and self.state_id.country_id.code == 'CA':
                self.lang = 'fr_CA'
            else:
                self.lang = 'en_US'
