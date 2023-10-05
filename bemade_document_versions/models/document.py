from odoo import models, fields, _, api, Command
from odoo.exceptions import ValidationError


class Document(models.Model):
    _inherit = 'documents.document'

    current_revision_id = fields.Many2one('documents.revision', 'Current Revision')
    revision_ids = fields.One2many('documents.revision', 'document_id')
    revision_sequence = fields.Many2one('ir.sequence',
                                        'Revision Sequence', )

    def set_up_revisions(self, initial_revision_name: str = None,
                         sequence_prefix: str = None,
                         sequence_suffix: str = None, sequence_padding: int = None):
        """
        Helper method to set up revisions, no matter how we got into tracking them.
        :param initial_revision_name str: The name to give to the initial revision. By
          default, this will be the next name from the sequence.
        :param sequence_prefix: The prefix to use for the new revision sequence.
        :param sequence_suffix: The suffix to use for the new revision sequence.
        :return None:
        """
        self.ensure_one()
        self.revision_sequence = self.revision_sequence or self._create_rev_sequence(
            sequence_prefix, sequence_suffix, sequence_padding)
        self.revision_ids = self.revision_ids or [Command.set(
            [self._create_first_revision(initial_revision_name).id])]

    def _create_rev_sequence(self, sequence_prefix: str = None,
                             sequence_suffix: str = None, sequence_padding: int = None):
        """
        Helper method to create a new sequence for a document that we are just starting
        to track revisions for.

        :param sequence_prefix: The prefix to use for the sequence.
        :param sequence_suffix: The suffix to use for the sequence.
        :param sequence_padding: The padding to use for the sequence.
        :return: The created ir.sequence record.
        """
        return self.env['ir.sequence'].create({
            'document_id': self.id,
            'name': f'sequence_doc{self.id}',
            'prefix': sequence_prefix,
            'suffix': sequence_suffix,
            'padding': sequence_padding,
            'implementation': 'standard',
        })

    def _create_first_revision(self, name: str = None):
        """
        Creates a new documents.revision record to associate to this Document

        :param name: Optional name to use for the newly created revision.
        :return: a single, new documents.revision record
        """
        self.ensure_one()
        name = name or self.revision_sequence.get_next_char(0)
        return self.env['documents.revision'].create({
            'document_id': self.id,
            'name': name,
            'attachment_id': self.attachment_id.id,
        })

    def get_next_revision_name(self):
        """
        :return str: The name of the next revision in the sequence or None if revision
        tracking is not yet set up.
        """
        return self.revision_sequence.get_next_char(self.revision_sequence._next())
