from odoo import models, fields, api

class Odoo2OdooSync(models.Model):
    _name = 'odoo2odoo.sync'
    _description = 'Synchronisation Odoo à Odoo'

    model_id = fields.Many2one(
        comodel_name='ir.model',
        string='Modèle Cible',
        required=True,
        help="Le modèle Odoo cible de la synchronisation."
    )

    res_id = fields.Integer(
        string='ID Ressource',
        required=True,
        help="L'ID de la ressource cible dans le modèle spécifié."
    )

    json_rpc_request = fields.Text(
        string='Requête JSON RPC',
        required=True,
        help="Le corps complet de la requête JSON RPC pour la synchronisation."
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Brouillon'),
            ('success', 'Succès'),
            ('failed', 'Échoué')
        ],
        string='État',
        default='draft',
        required=True,
        help="L'état de la tentative de synchronisation."
    )

    last_attempt = fields.Datetime(
        string='Dernière Tentative',
        help="La date et l'heure de la dernière tentative de synchronisation."
    )

    confirmation = fields.Datetime(
        string='Confirmation',
        help="La date et l'heure de la confirmation de la synchronisation réussie."
    )

