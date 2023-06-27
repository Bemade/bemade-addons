from odoo.tests import TransactionCase, HttpCase, tagged
from odoo import Command
from test_bemade_fsm_common import FSMManagerUserTransactionCase

class SaleOrderFSMContactsCase(FSMManagerUserTransactionCase):

    def test_default_site_contacts(self):
        # Make sure the SO pulls the defaults from the partner correctly
        pass

    def test_default_billing_contacts(self):
        # Make sure the SO pulls the defaults from the partner correctly
        pass

    def test_default_workorder_contacts(self):
        # Make sure the SO pulls the defaults from the partner correctly
        pass

    def test_change_site_contacts(self):
        # Make sure the SO contacts can be updated without feeding back to the partner
        pass

    def test_change_workorder_contacts(self):
        # Make sure the SO contacts can be updated without feeding back to the partner
        pass

    def test_change_billing_contacts(self):
        # Make sure the SO contacts can be updated without feedin back to the partner
        pass

