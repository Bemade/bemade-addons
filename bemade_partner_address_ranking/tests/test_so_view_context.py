# Copyright (C) 2024 Bemade Inc. (<https://www.bemade.org>).
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
"""
Acceptance criteria for bemade_partner_address_ranking SO view context tests
=============================================================================

1.  Ranking key is injected (delivery): partner_shipping_id context contains
    partner_address_ranking == 'delivery' after _get_view.
2.  Ranking key is injected (invoice): partner_invoice_id context contains
    partner_address_ranking == 'invoice' after _get_view.
3.  Consuming view's show_address intent is PRESERVED: a test-only inheriting
    view that sets show_address: True on partner_shipping_id keeps that value
    alongside partner_address_ranking: 'delivery'.
4.  No show_address: False is forced by this module: the module never introduces
    a show_address token of its own — only core's defaults remain.
5.  #1126 case — address still displays when partner_id == partner_shipping_id:
    display_name with show_address=True includes street and city.
6.  name_search ranking still fires via the injected key.
7.  View integrity / no broken arch: get_view does not raise; deleted
    view_order_form_address_ranking external id no longer resolves.
"""
import ast

from lxml import etree

from odoo.tests.common import TransactionCase


def _parse_context(ctx_str):
    """Best-effort parse of an Odoo context attribute string.

    The string may reference bare names like ``partner_id`` which are not valid
    Python literals.  We replace unknown names with None so that ast.literal_eval
    can proceed, allowing us to inspect the keys that *are* literal strings.

    The string is stripped before parsing because Odoo's view combiner may
    return multiline indented attribute values; ast.literal_eval rejects
    lines that look like unexpected indentation.
    """
    import re

    # Strip leading/trailing whitespace (incl. newlines from multiline arch attrs)
    ctx_str = ctx_str.strip()

    # Replace bare identifiers (not quoted, not preceded by : or a quote) with None
    safe = re.sub(
        r"(?<!['\"\w])([a-zA-Z_][a-zA-Z0-9_]*)(?!['\"\w])",
        lambda m: m.group(1) if m.group(1) in ("True", "False", "None") else "None",
        ctx_str,
    )
    try:
        return ast.literal_eval(safe)
    except Exception:
        return {}


class TestSOViewContext(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SaleOrder = cls.env["sale.order"]
        # Get the main SO form view arch once for re-use in arch tests.
        arch_node, _view = cls.SaleOrder._get_view(view_type="form")
        cls.arch = arch_node

    # ------------------------------------------------------------------
    # Test 1 – Ranking key injected: delivery
    # ------------------------------------------------------------------
    def test_ranking_key_delivery(self):
        """partner_shipping_id context must contain partner_address_ranking == 'delivery'."""
        nodes = self.arch.xpath("//field[@name='partner_shipping_id']")
        self.assertTrue(nodes, "partner_shipping_id field not found in SO form arch")
        # Check at least one node carries the key (may be multiple due to hidden variant)
        found = False
        for node in nodes:
            ctx_str = node.get("context", "")
            if "partner_address_ranking" in ctx_str:
                parsed = _parse_context(ctx_str)
                self.assertEqual(
                    parsed.get("partner_address_ranking"),
                    "delivery",
                    "partner_shipping_id context must map partner_address_ranking to 'delivery'",
                )
                found = True
        self.assertTrue(found, "No partner_shipping_id node had partner_address_ranking injected")

    # ------------------------------------------------------------------
    # Test 2 – Ranking key injected: invoice
    # ------------------------------------------------------------------
    def test_ranking_key_invoice(self):
        """partner_invoice_id context must contain partner_address_ranking == 'invoice'."""
        nodes = self.arch.xpath("//field[@name='partner_invoice_id']")
        self.assertTrue(nodes, "partner_invoice_id field not found in SO form arch")
        found = False
        for node in nodes:
            ctx_str = node.get("context", "")
            if "partner_address_ranking" in ctx_str:
                parsed = _parse_context(ctx_str)
                self.assertEqual(
                    parsed.get("partner_address_ranking"),
                    "invoice",
                    "partner_invoice_id context must map partner_address_ranking to 'invoice'",
                )
                found = True
        self.assertTrue(found, "No partner_invoice_id node had partner_address_ranking injected")

    # ------------------------------------------------------------------
    # Test 3 – Consuming view's show_address is PRESERVED
    # ------------------------------------------------------------------
    def test_consuming_view_show_address_preserved(self):
        """A consuming view that sets show_address: True must not be clobbered.

        This is the core regression guard: under the old XML-rewrite design this
        test would have FAILED because the module's view replaced the whole dict.
        """
        # Create a test-only inheriting view with show_address: True (no ranking key)
        consumer_view = self.env["ir.ui.view"].create(
            {
                "name": "test.so.form.show_address_consumer",
                "model": "sale.order",
                "inherit_id": self.env.ref("sale.view_order_form").id,
                "priority": 99,
                "arch": """
                    <xpath expr="//field[@name='partner_shipping_id'][@groups='account.group_delivery_invoice_address']"
                           position="attributes">
                        <attribute name="context">
                            {'default_type': 'delivery', 'show_address': True,
                             'default_parent_id': partner_id}
                        </attribute>
                    </xpath>
                """,
            }
        )
        self.addCleanup(consumer_view.unlink)

        # Re-render the arch with the consumer view active.
        # load_all_views=True is required when tests run during module loading
        # (pool._init is True), because _filter_loaded_views() otherwise
        # strips out views that have no ir_model_data entry — which includes
        # views created programmatically in tests.
        so = self.SaleOrder.with_context(load_all_views=True)
        arch, _view = so._get_view(view_type="form")

        # Find the groups-gated shipping node that the consumer view targets
        nodes = arch.xpath(
            "//field[@name='partner_shipping_id']"
            "[@groups='account.group_delivery_invoice_address']"
        )
        self.assertTrue(nodes, "groups-gated partner_shipping_id node not found")
        node = nodes[0]
        ctx_str = node.get("context", "")

        # Both keys must be present
        self.assertIn(
            "partner_address_ranking",
            ctx_str,
            "partner_address_ranking must be injected even when consumer set show_address",
        )
        self.assertIn(
            "show_address",
            ctx_str,
            "show_address must survive after _get_view injection",
        )
        parsed = _parse_context(ctx_str)
        self.assertEqual(
            parsed.get("partner_address_ranking"),
            "delivery",
            "partner_address_ranking must be 'delivery'",
        )
        self.assertEqual(
            parsed.get("show_address"),
            True,
            "show_address must remain True as set by the consuming view",
        )

    # ------------------------------------------------------------------
    # Test 4 – Module never forces show_address: False
    # ------------------------------------------------------------------
    def test_module_does_not_force_show_address_false(self):
        """The module must not override core's show_address value.

        With no consuming view, core's base ``sale.view_order_form`` already
        sets ``show_address: False`` on the address picker nodes.  The module's
        only job is to *add* the ``partner_address_ranking`` key without touching
        anything else.  We assert:

        * ``partner_address_ranking`` is present (the module did inject its key).
        * ``show_address`` equals ``False`` — core's default is preserved
          unchanged; the module did not flip it to True or remove it.

        This assertion would fail if the old XML-rewrite design were still active
        AND somehow set show_address to a different value, but the primary
        regression guard for show_address preservation is test_consuming_view_
        show_address_preserved (test 3).
        """
        arch, _view = self.SaleOrder._get_view(view_type="form")
        for field_name in ("partner_shipping_id", "partner_invoice_id"):
            nodes = arch.xpath(
                f"//field[@name='{field_name}']"
                "[@groups='account.group_delivery_invoice_address']"
            )
            if not nodes:
                continue
            ctx_str = nodes[0].get("context", "")
            parsed = _parse_context(ctx_str)
            # The module must have injected partner_address_ranking
            self.assertIn(
                "partner_address_ranking",
                ctx_str,
                f"{field_name} context must contain partner_address_ranking",
            )
            # Core's show_address: False must be present and unchanged
            # (the module never asserts show_address itself — only core does)
            self.assertEqual(
                parsed.get("show_address"),
                False,
                f"{field_name} context show_address must equal core's default False "
                f"(module must not override it)",
            )

    # ------------------------------------------------------------------
    # Test 5 – #1126 regression: address shows even when ship-to == customer
    # ------------------------------------------------------------------
    def test_display_name_with_show_address(self):
        """With show_address=True the address block renders even when ship-to == customer."""
        company = self.env["res.partner"].create(
            {
                "name": "Test Company 3724",
                "is_company": True,
                "street": "123 Main St",
                "city": "Montreal",
                "country_id": self.env.ref("base.ca").id,
            }
        )
        display = company.with_context(show_address=True).display_name
        self.assertIn(
            "123 Main St",
            display,
            "display_name with show_address=True must include the street",
        )
        self.assertIn(
            "Montreal",
            display,
            "display_name with show_address=True must include the city",
        )

    # ------------------------------------------------------------------
    # Test 6 – name_search ranking still fires via injected key
    # ------------------------------------------------------------------
    def test_name_search_ranking_via_injected_key(self):
        """name_search must rank by usage when partner_address_ranking is in context."""
        company = self.env["res.partner"].create(
            {"name": "Test Ranking Company 3724", "is_company": True}
        )
        addr_used = self.env["res.partner"].create(
            {
                "name": "Delivery Used",
                "parent_id": company.id,
                "type": "delivery",
            }
        )
        addr_unused = self.env["res.partner"].create(
            {
                "name": "Delivery Unused",
                "parent_id": company.id,
                "type": "delivery",
            }
        )
        # Confirm a SO using addr_used
        so = self.env["sale.order"].create(
            {
                "partner_id": company.id,
                "partner_invoice_id": company.id,
                "partner_shipping_id": addr_used.id,
            }
        )
        so.action_confirm()

        results = (
            self.env["res.partner"]
            .with_context(
                partner_address_ranking="delivery",
                default_commercial_partner_id=company.id,
            )
            .name_search("")
        )
        result_ids = [r[0] for r in results]
        self.assertIn(addr_used.id, result_ids, "Used address must appear in name_search results")
        self.assertIn(addr_unused.id, result_ids, "Unused address must appear in name_search results")
        # The used address must rank before the unused one
        if addr_used.id in result_ids and addr_unused.id in result_ids:
            self.assertLess(
                result_ids.index(addr_used.id),
                result_ids.index(addr_unused.id),
                "Used delivery address must rank first in name_search",
            )

    # ------------------------------------------------------------------
    # Test 7 – View integrity and deleted external id
    # ------------------------------------------------------------------
    def test_view_integrity_and_deleted_xml_id(self):
        """get_view must not raise; deleted XML id must no longer resolve."""
        # Calling get_view should succeed without exceptions
        result = self.SaleOrder.get_view(view_type="form")
        self.assertIn("arch", result, "get_view must return an arch key")

        # The deleted XML record must not exist
        old_view = self.env.ref(
            "bemade_partner_address_ranking.view_order_form_address_ranking",
            raise_if_not_found=False,
        )
        self.assertFalse(
            old_view,
            "view_order_form_address_ranking external id must not resolve after deletion",
        )
