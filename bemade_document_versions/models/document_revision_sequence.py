from odoo import models, fields, api, _

class DocumentRevisionSequence(models.Model):
    _inherit = 'ir.sequence'
    # Would prefer to inherit and make a new model, but the way ir.sequence is
    # implemented has a lot of hard coded references to "ir.sequence" for all the
    # database operations.

    document_id = fields.Many2one('documents.document', 'Document',
                                  ondelete='cascade')

    def predict_next_id(self, sequence_date=None):
        self.check_access_rights('read')
        return self._predict_next(sequence_date=sequence_date)

    def _predict_next(self, sequence_date=None):
        if not self.use_date_range:
            return self.get_next_char(self.number_next_actual)
        raise NotImplementedError(
            _('_predict_next is not implemented for date sequences.'))
