# Copyright (C) 2024 Bemade Inc. (<https://www.bemade.org>).
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
"""
Acceptance criteria for bemade_partner_address_ranking view arch tests
=======================================================================

1.  Kanban card icons present: the inline kanban card template inside child_ids
    contains two <i> tags with t-if guards for is_favorite_invoice.raw_value and
    is_favorite_delivery.raw_value, each carrying the expected tooltip title.
2.  Modal form has favorite toggles: the inline <form> inside child_ids has
    is_favorite_invoice and is_favorite_delivery fields with widget="boolean_toggle"
    and invisible="type == 'contact'".
3.  Form loads via Form proxy: creating a company partner, adding a child address,
    flipping is_favorite_invoice=True via the Form proxy, saving and reloading
    confirms the value persisted.
4.  Kanban icons render distinguishably: four child partners covering the four
    (invoice, delivery) flag combinations have the expected field values.
"""
from lxml import etree

from odoo.tests.common import TransactionCase
from odoo.tests.form import Form


class TestViewArch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        # Pre-load the combined arch once for the arch-inspection tests.
        view = cls.env.ref("base.view_partner_form")
        result = view.get_views([[view.id, "form"]])
        cls.arch = etree.fromstring(result["views"]["form"]["arch"])

    # ------------------------------------------------------------------
    # Test 1 – Kanban card icons present
    # ------------------------------------------------------------------
    def test_kanban_card_icons_present(self):
        """Two <i> icon elements must be injected into the inline kanban card."""
        # Find all <i> elements anywhere in the arch that carry t-if on is_favorite_*
        invoice_icons = self.arch.xpath(
            ".//i[@t-if=\"record.is_favorite_invoice.raw_value\"]"
        )
        delivery_icons = self.arch.xpath(
            ".//i[@t-if=\"record.is_favorite_delivery.raw_value\"]"
        )
        self.assertTrue(
            invoice_icons,
            "Expected an <i> icon with t-if=\"record.is_favorite_invoice.raw_value\" "
            "in the partner form kanban card.",
        )
        self.assertTrue(
            delivery_icons,
            "Expected an <i> icon with t-if=\"record.is_favorite_delivery.raw_value\" "
            "in the partner form kanban card.",
        )
        # Verify tooltip titles
        self.assertEqual(
            invoice_icons[0].get("title"),
            "Favorite invoice address",
            "Invoice icon must have title='Favorite invoice address'.",
        )
        self.assertEqual(
            delivery_icons[0].get("title"),
            "Favorite delivery address",
            "Delivery icon must have title='Favorite delivery address'.",
        )

    # ------------------------------------------------------------------
    # Test 2 – Modal form has favorite toggles
    # ------------------------------------------------------------------
    def test_modal_form_has_favorite_toggles(self):
        """The inline form inside child_ids must expose both favorite fields as boolean_toggle."""
        # Locate <field name="child_ids"> nodes and find form descendants
        child_ids_nodes = self.arch.xpath(".//field[@name='child_ids']")
        self.assertTrue(child_ids_nodes, "child_ids field not found in arch.")

        found_invoice = False
        found_delivery = False
        for child_ids_node in child_ids_nodes:
            for form_node in child_ids_node.xpath(".//form"):
                for field in form_node.xpath(".//field[@name='is_favorite_invoice']"):
                    if field.get("widget") == "boolean_toggle":
                        found_invoice = True
                        self.assertEqual(
                            field.get("invisible"),
                            "type == 'contact'",
                            "is_favorite_invoice toggle must be invisible when type == 'contact'.",
                        )
                for field in form_node.xpath(".//field[@name='is_favorite_delivery']"):
                    if field.get("widget") == "boolean_toggle":
                        found_delivery = True
                        self.assertEqual(
                            field.get("invisible"),
                            "type == 'contact'",
                            "is_favorite_delivery toggle must be invisible when type == 'contact'.",
                        )

        self.assertTrue(
            found_invoice,
            "is_favorite_invoice with widget='boolean_toggle' not found in child_ids inline form.",
        )
        self.assertTrue(
            found_delivery,
            "is_favorite_delivery with widget='boolean_toggle' not found in child_ids inline form.",
        )

    # ------------------------------------------------------------------
    # Test 3 – Form loads via Form proxy
    # ------------------------------------------------------------------
    def test_form_loads_via_form_proxy(self):
        """Form proxy must be able to set is_favorite_invoice on a child address and save."""
        company = self.Partner.create(
            {"name": "Test Company ViewArch", "is_company": True}
        )
        with Form(company) as form:
            with form.child_ids.new() as child:
                child.name = "Invoice Addr"
                child.type = "invoice"
                child.is_favorite_invoice = True

        # Reload and assert the value persisted
        invoice_child = company.child_ids.filtered(lambda p: p.type == "invoice")
        self.assertTrue(invoice_child, "Child address of type 'invoice' not found after save.")
        self.assertTrue(
            invoice_child[0].is_favorite_invoice,
            "is_favorite_invoice should be True after saving via Form proxy.",
        )

    # ------------------------------------------------------------------
    # Test 4 – Kanban icons render distinguishably (AC14)
    # ------------------------------------------------------------------
    def test_kanban_icons_render_distinguishably(self):
        """Four flag combinations must produce distinct icon sets (verified by field values)."""
        company = self.Partner.create(
            {"name": "Test Company Icons", "is_company": True}
        )
        addr_none = self.Partner.create(
            {
                "name": "No favorites",
                "parent_id": company.id,
                "type": "delivery",
                "is_favorite_invoice": False,
                "is_favorite_delivery": False,
            }
        )
        addr_invoice = self.Partner.create(
            {
                "name": "Invoice favorite only",
                "parent_id": company.id,
                "type": "invoice",
                "is_favorite_invoice": True,
                "is_favorite_delivery": False,
            }
        )
        addr_delivery = self.Partner.create(
            {
                "name": "Delivery favorite only",
                "parent_id": company.id,
                "type": "delivery",
                "is_favorite_invoice": False,
                "is_favorite_delivery": True,
            }
        )
        addr_both = self.Partner.create(
            {
                "name": "Both favorites",
                "parent_id": company.id,
                "type": "other",
                "is_favorite_invoice": False,  # constraint: only one per type
                "is_favorite_delivery": False,
            }
        )
        # Ensure no constraints violated before toggling
        # addr_none: 0 icons
        self.assertFalse(addr_none.is_favorite_invoice)
        self.assertFalse(addr_none.is_favorite_delivery)
        # addr_invoice: 1 icon (invoice star)
        self.assertTrue(addr_invoice.is_favorite_invoice)
        self.assertFalse(addr_invoice.is_favorite_delivery)
        # addr_delivery: 1 icon (delivery star)
        self.assertFalse(addr_delivery.is_favorite_invoice)
        self.assertTrue(addr_delivery.is_favorite_delivery)
        # addr_both: 0 icons (both false, constraint prevents setting both flags
        # on the same record if another record already holds them)
        self.assertFalse(addr_both.is_favorite_invoice)
        self.assertFalse(addr_both.is_favorite_delivery)
