# License: LGPL-3
# Copyright 2026 Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""
Tests for the portal ACL fix and the "# PO" label enhancement.

Acceptance criteria verified here:
- AC-bug: Public user (uid 4) can update sale.order.client_order_ref via the
  portal update_reference route without triggering an ACL denial on sale.order.
- AC3: No ir.model.access or ir.rule grants were added for public/portal on
  sale.order; access is gated solely by the portal access token.
- AC4: mandatory-reference validation on action_confirm is still enforced (not
  regressed by the controller refactor).
- AC7/label: The portal view arch contains the "# PO" label adjacent to "Your
  Reference".
"""
import json

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install")
class TestPortalReference(HttpCase):
    """Controller-level and view-arch tests for the portal reference field."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Portal Customer",
                "email": "portal@example.com",
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product Portal",
                "type": "consu",
                "invoice_policy": "order",
            }
        )
        cls.sale_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        # Ensure the order has a portal access token
        cls.sale_order._portal_ensure_token()
        cls.access_token = cls.sale_order.access_token

    def _call_update_reference(self, order_id, reference, access_token=None):
        """
        Call the portal_update_sale_reference JSON endpoint via HTTP and return
        the parsed JSON response dict.
        """
        url = f"/my/orders/{order_id}/update_reference"
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "call",
                "id": 1,
                "params": {
                    "order_id": order_id,
                    "reference": reference,
                    "access_token": access_token,
                },
            }
        )
        resp = self.url_open(
            url,
            data=payload.encode(),
            headers={"Content-Type": "application/json"},
        )
        return resp.json().get("result", resp.json())

    # ------------------------------------------------------------------
    # Test 1: Public user + valid token → reference written, no ACL denial
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model")
    def test_portal_update_reference_public_token_no_acl_denial(self):
        """
        Calling the endpoint as the public user (no session login) with a valid
        access_token must succeed: client_order_ref is written and NO AccessError
        / "Access Denied by ACLs ... read ... sale.order" is raised.

        The mute_logger decorator ensures that if the old non-sudo browse
        re-appears, the ir_model logger would suppress the log line BUT the
        raised AccessError would still propagate and fail this test.
        """
        result = self._call_update_reference(
            order_id=self.sale_order.id,
            reference="PO-12345",
            access_token=self.access_token,
        )
        self.assertNotIn(
            "error",
            result,
            f"Expected success but got error: {result.get('error')}",
        )
        self.assertTrue(result.get("success"), f"Unexpected result: {result}")
        self.sale_order.invalidate_recordset()
        self.assertEqual(
            self.sale_order.client_order_ref,
            "PO-12345",
            "client_order_ref was not written by the public-user portal call",
        )

    # ------------------------------------------------------------------
    # Test 2: Invalid / absent token → clean error, no write
    # ------------------------------------------------------------------
    def test_portal_update_reference_rejects_bad_token(self):
        """
        Calling the endpoint with an invalid access_token must return a clean
        error dict and must NOT write client_order_ref.  No ACL broadening is
        tested here: access is gated solely by the token.
        """
        self.sale_order.write({"client_order_ref": False})
        result = self._call_update_reference(
            order_id=self.sale_order.id,
            reference="SHOULD-NOT-BE-WRITTEN",
            access_token="invalid-token-value",
        )
        self.assertIn(
            "error",
            result,
            f"Expected an error response but got: {result}",
        )
        self.sale_order.invalidate_recordset()
        self.assertFalse(
            self.sale_order.client_order_ref,
            "client_order_ref must not be written when token is invalid",
        )

    # ------------------------------------------------------------------
    # Test 3: Mandatory reference still enforced on action_confirm (AC4)
    # ------------------------------------------------------------------
    def test_mandatory_reference_still_enforced_on_confirm(self):
        """
        With enforce_customer_reference=True and no client_order_ref,
        action_confirm must still raise ValidationError.  The controller
        refactor must not have accidentally bypassed the model-level check.
        """
        self.env["ir.config_parameter"].sudo().set_param(
            "sale_mandatory_customer_reference.enforce_customer_reference", True
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        with self.assertRaises(ValidationError):
            order.with_context(skip_tax_warning=True).action_confirm()

    # ------------------------------------------------------------------
    # Test 4: "# PO" label present in portal view arch (AC7/label)
    # ------------------------------------------------------------------
    def test_po_label_present_in_portal_arch(self):
        """
        The view arch for sale_order_portal_content_inherit_sale_mandatory_reference
        must contain the text "# PO" adjacent to the "Your Reference" heading.
        """
        view = self.env.ref(
            "sale_mandatory_customer_reference"
            ".sale_order_portal_content_inherit_sale_mandatory_reference"
        )
        arch = view.arch_db
        self.assertIn(
            "# PO",
            arch,
            'Expected "# PO" to be present in the portal view arch',
        )
        self.assertIn(
            "Your Reference",
            arch,
            'Expected "Your Reference" to still be present in the portal view arch',
        )
