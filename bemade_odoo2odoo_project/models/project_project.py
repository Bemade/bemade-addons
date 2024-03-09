from odoo import models, fields, api

class Project(models.Model):
    _inherit = 'project.project'  # Héritage du modèle projet existant

    customer_project_id = fields.Integer(
        string="ID Projet Client",
        required=False,
        help="L'ID du projet dans le système client."
    )

    customer_odoo_server = fields.Char(string="Serveur Odoo Client")
    customer_username = fields.Char(string="Nom d'usager Client")
    customer_password = fields.Char(string="Mot de passe Client", invisible=True)

    odoo2odoo_sync_ids = fields.One2many(
        comodel_name='odoo2odoo.sync',
        inverse_name='project_id',
        string='Synchronisations'
    )

    last_push = fields.Datetime(
        string="Dernière Tentative de Synchronisation",
        compute="_compute_sync_status",
        store=True
    )

    last_push_completed = fields.Datetime(
        string="Dernière Synchronisation Réussie",
        compute="_compute_sync_status",
        store=True
    )

    last_updated = fields.Datetime(
        string="Dernière Mise à Jour par Bébé",
        ompute="_compute_sync_status",
        store=True
    )

    odoo2odoo_sync_count = fields.Integer(
        string="Nombre de Synchronisations",
        compute="_compute_sync_status"
    )

    odoo2odoo_sync_completed_count = fields.Integer(
        string="Nombre de Synchronisations Réussies",
        compute="_compute_sync_status"
    )

    @api.model
    def create(self, vals):
        # Appel de la méthode super() pour créer le projet dans Odoo.
        new_project = super(Project, self).create(vals)

        if 'customer_odoo_server' in vals and vals['customer_odoo_server']:
            # Simulation de données pour la synchronisation avec le système "bébé".
            # Vous adapterez cette partie selon votre logique spécifique de synchronisation.
            json_rpc_request = json.dumps({
                "jsonrpc": "2.0",
                "method": "create_project",
                "params": {
                    "name": new_project.name,
                    # Ajoutez d'autres paramètres nécessaires pour la création du projet dans le système "bébé".
                },
            })

            # Création d'un enregistrement dans odoo2odoo.sync pour suivre la tentative de synchronisation.
            self.env['odoo2odoo.sync'].create({
                'model_id': self.env.ref('base.model_project_project').id,
                'res_id': new_project.id,
                'json_rpc_request': json_rpc_request,
                'state': 'draft',  # Commencez avec l'état 'draft' pour la nouvelle synchronisation.
            })
        return new_project

    @api.depends('odoo2odoo_sync_ids.state')
    def _compute_sync_status(self):
        for project in self:
            sync_records = self.env['odoo2odoo.sync'].search([
                ('model_id.model', '=', 'project.project'),
                ('res_id', '=', project.id),
            ], order='last_attempt desc')
            project.odoo2odoo_sync_count = len(sync_records)
            if sync_records:
                project.odoo2odoo_sync_completed_count = len(sync_records.filtered(lambda r: r.state == 'success'))
                project.last_push = sync_records[0].last_attempt
                success_records = sync_records.filtered(lambda r: r.state == 'success')
                if success_records:
                    project.last_push_completed = success_records[0].last_attempt
                # Assume that 'last_updated' reflects the last successful pull from 'bébé'
                # This requires additional logic to track when updates are received from the bébé system
                project.last_updated = success_records[0].confirmation if success_records else False