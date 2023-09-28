from odoo import models, fields, _, api, Command
from odoo.exceptions import ValidationError


class Document(models.Model):
    _inherit = ['documents.document']

    current_revision_id = fields.Many2one('documents.revision', 'Current Revision')
    revision_ids = fields.One2many('documents.revision', 'document_id')
    revision_sequence = fields.Many2one('documents.revision.sequence', 'document_id',
                                        'Revision Sequence', )
    track_revisions = fields.Boolean(default=False)
    # set copy=False for number_next
    number_next = fields.Integer(string='Next Number', required=True, default=1,
                                 copy=False, help="Next number of this sequence")

    @api.constrains('revision_ids', 'revision_sequence', 'track_revisions')
    def constrain_revisions(self):
        for rec in self:
            revision_fields = [rec.revision_ids, rec.revision_sequence,
                               rec.track_revisions]
            if any(revision_fields) and not all(revision_fields):
                raise ValidationError(_('A revision sequence must be selected to track'
                                        ' revisions.'))

    def write(self, vals):
        super().write(vals)
        if self.track_revisions and 'track_revisions' in vals \
                and not vals['track_revisions']:
            raise ValidationError(_('Revision tracking cannot be disabled after it has'
                                    'been turned on for a document.'))
        self._check_revision_fields()

    @api.model_create_multi
    def create(self, vals):
        res = super().create(vals)
        for rec in res:
            rec._check_revision_fields()
        return res

    def _check_revision_fields(self):
        """ Helper method to check that all three fields `track_revisions`,
        `revisions_sequence` and `revision_ids` are properly set if any one of them is set.
        :return: None
        """
        self.ensure_one()
        revision_fields = [self.revision_ids, self.revision_sequence,
                           self.track_revisions]
        if any(revision_fields) and not all(revision_fields):
            self._set_up_revisions()

    def _set_up_revisions(self):
        """
        Helper method to set up revisions, no matter how we got into tracking them.
        :return: None
        """
        self.ensure_one()
        self.track_revisions = True  # may already be true, but no matter
        self.revision_sequence = self.revision_sequence or self.env.ref(
            'bemade_document_versions.document_revision_sequence_default')
        self.revision_ids = self.revision_ids or Command.set(
            [self._create_first_revision()])

    def _create_first_revision(self):
        """
        Creates a new documents.revision record to associate to this Document
        :return: a single, new documents.revision record
        """
        self.ensure_one()
        return self.env['documents.revision'].create({'document_id': self.id, })
