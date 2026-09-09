# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from markupsafe import Markup


class TestProductSupplierinfoTracking(TransactionCase):

    def setUp(self):
        super().setUp()

        # Use existing data to avoid database constraint issues
        self.partner_supplier = self.env["res.partner"].create(
            {
                "name": "Test Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )

        # Use first available product template and variant
        self.product_template = self.env["product.template"].search([], limit=1)
        if not self.product_template:
            self.skipTest("No product template available for testing")

        self.product_variant = (
            self.product_template.product_variant_ids[0]
            if self.product_template.product_variant_ids
            else None
        )

        self.currency_usd = self.env.ref("base.USD")
        self.uom_unit = self.env.ref("uom.product_uom_unit")

    def test_supplierinfo_tracking_fields(self):
        """Test that tracking is enabled on all expected fields"""
        supplierinfo = self.env["product.supplierinfo"].create(
            {
                "partner_id": self.partner_supplier.id,
                "product_tmpl_id": self.product_template.id,
                "min_qty": 10.0,
                "price": 100.0,
                "currency_id": self.currency_usd.id,
                "product_name": "Supplier Product Name",
                "product_code": "SUP001",
                "delay": 5,
            }
        )

        # Check that the model inherits from mail.thread
        self.assertTrue(hasattr(supplierinfo, "message_ids"))
        self.assertTrue(hasattr(supplierinfo, "activity_ids"))

        # Verify tracking fields are properly set
        tracked_fields = [
            "partner_id",
            "product_name",
            "product_code",
            "product_uom",
            "min_qty",
            "currency_id",
            "date_start",
            "date_end",
            "product_id",
            "product_tmpl_id",
            "delay",
            "price",
            "discount",
        ]

        for field_name in tracked_fields:
            field = supplierinfo._fields.get(field_name)
            self.assertTrue(
                field.tracking, f"Field {field_name} should have tracking enabled"
            )

    def test_chatter_message_generation_on_write(self):
        """Test that chatter messages are generated when supplierinfo is updated"""
        # Create a supplierinfo record
        supplierinfo = self.env["product.supplierinfo"].create(
            {
                "partner_id": self.partner_supplier.id,
                "product_tmpl_id": self.product_template.id,
                "product_id": (
                    self.product_variant.id if self.product_variant else False
                ),
                "min_qty": 1.0,
                "price": 10.0,
            }
        )

        # Clear any existing messages
        if self.product_template:
            self.product_template.message_ids.unlink()
        if self.product_variant:
            self.product_variant.message_ids.unlink()

        # Update the supplierinfo to trigger chatter
        supplierinfo.write(
            {
                "price": 15.0,
                "min_qty": 2.0,
            }
        )

        # Check that messages were posted to product template
        if self.product_template:
            template_messages = self.product_template.message_ids
            self.assertTrue(
                len(template_messages) > 0,
                "Should have posted message to product template",
            )

        # Check that messages were posted to product variant if it exists
        if self.product_variant:
            variant_messages = self.product_variant.message_ids
            self.assertTrue(
                len(variant_messages) > 0,
                "Should have posted message to product variant",
            )

        # Verify message content contains the changes
        message_body = template_messages[0].body
        self.assertIn("Price modified", message_body)
        self.assertIn("min_qty", message_body)

    def test_chatter_message_content_structure(self):
        """Test the structure and content of generated chatter messages"""
        supplierinfo = self.env["product.supplierinfo"].create(
            {
                "partner_id": self.partner_supplier.id,
                "product_tmpl_id": self.product_template.id,
                "product_id": (
                    self.product_variant.id if self.product_variant else False
                ),
                "min_qty": 5.0,
                "price": 75.0,
                "date_start": "2024-01-01",
                "date_end": "2024-12-31",
            }
        )

        # Clear existing messages
        if self.product_template:
            self.product_template.message_ids.unlink()
        if self.product_variant:
            self.product_variant.message_ids.unlink()

        # Update to trigger chatter message
        supplierinfo.write({"price": 80.0, "min_qty": 10.0})

        # Check that messages were created
        if self.product_template:
            template_messages = self.product_template.message_ids
            self.assertTrue(
                len(template_messages) > 0,
                "Should have posted message to product template",
            )

            # Verify message content structure
            message_body = template_messages[0].body
            self.assertIn("Price modified", message_body)
            self.assertIn("price --&gt; 80.0", message_body)
            self.assertIn("min_qty --&gt; 10.0", message_body)

    def test_chatter_message_without_variant(self):
        """Test chatter message generation when no product variant is specified"""
        # Create supplierinfo without variant
        supplierinfo = self.env["product.supplierinfo"].create(
            {
                "partner_id": self.partner_supplier.id,
                "product_tmpl_id": self.product_template.id,
                "min_qty": 1.0,
                "price": 50.0,
            }
        )

        # Clear existing messages
        if self.product_template:
            self.product_template.message_ids.unlink()

        # Update to trigger chatter message
        supplierinfo.write({"price": 60.0})

        # Verify message was posted to template
        if self.product_template:
            template_messages = self.product_template.message_ids
            self.assertTrue(
                len(template_messages) > 0, "Should post message to template"
            )

            # Verify message content
            message_body = template_messages[0].body
            self.assertIn("Price modified", message_body)
            self.assertIn("price --&gt; 60.0", message_body)

    def test_supplierinfo_show_details_action(self):
        """Test the supplierinfo_show_details action method"""
        supplierinfo = self.env["product.supplierinfo"].create(
            {
                "partner_id": self.partner_supplier.id,
                "product_tmpl_id": self.product_template.id,
                "product_id": self.product_variant.id,
                "min_qty": 1.0,
                "price": 25.0,
            }
        )

        action = supplierinfo.supplierinfo_show_details()

        # Verify action structure
        self.assertEqual(action["name"], "Supplier price")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["res_model"], "product.supplierinfo")
        self.assertEqual(action["res_id"], supplierinfo.id)
        self.assertEqual(action["type"], "ir.actions.act_window")

        # Verify domain
        expected_domain = [
            ("product_tmpl_id", "=", self.product_template.id),
            (
                "product_id",
                "=",
                self.product_variant.id if self.product_variant else False,
            ),
        ]
        self.assertEqual(action["domain"], expected_domain)

    def test_multiple_supplierinfo_tracking(self):
        """Test tracking with multiple supplierinfo records"""
        supplierinfo1 = self.env["product.supplierinfo"].create(
            {
                "partner_id": self.partner_supplier.id,
                "product_tmpl_id": self.product_template.id,
                "min_qty": 1.0,
                "price": 10.0,
            }
        )

        supplier2 = self.env["res.partner"].create(
            {
                "name": "Second Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )

        supplierinfo2 = self.env["product.supplierinfo"].create(
            {
                "partner_id": supplier2.id,
                "product_tmpl_id": self.product_template.id,
                "min_qty": 5.0,
                "price": 8.0,
            }
        )

        # Clear existing messages
        self.product_template.message_ids.unlink()

        # Modify both
        supplierinfo1.write({"price": 12.0})
        supplierinfo2.write({"price": 9.0})

        # Should have messages for both modifications (may include tracking messages
        # from mail.thread in addition to the custom chatter messages)
        messages = self.product_template.message_ids
        self.assertGreaterEqual(
            len(messages), 2, "Should have messages for both supplierinfo modifications"
        )

    def test_chatter_message_with_minimal_data(self):
        """Test chatter message generation with minimal supplierinfo data"""
        # Create minimal supplierinfo
        supplierinfo = self.env["product.supplierinfo"].create(
            {
                "partner_id": self.partner_supplier.id,
                "product_tmpl_id": self.product_template.id,
                "price": 25.0,
            }
        )

        # Clear existing messages
        if self.product_template:
            self.product_template.message_ids.unlink()

        # Update to trigger chatter message
        supplierinfo.write({"price": 30.0})

        # Verify basic message structure
        if self.product_template:
            template_messages = self.product_template.message_ids
            self.assertTrue(len(template_messages) > 0, "Should have posted message")

            message_body = template_messages[0].body
            self.assertIn("Price modified", message_body)
            self.assertIn("price --&gt; 30.0", message_body)
            # Should not contain qty, dates since they weren't set
            self.assertNotIn("Minimum qty", message_body)
            self.assertNotIn("Starting", message_body)
            self.assertNotIn("Ending", message_body)

    def test_inheritance_structure(self):
        """Test that the model properly inherits required mixins"""
        supplierinfo = self.env["product.supplierinfo"]

        # Check inheritance
        self.assertIn("mail.thread", supplierinfo._inherit)
        self.assertIn("mail.activity.mixin", supplierinfo._inherit)
        self.assertIn("product.supplierinfo", supplierinfo._inherit)

        # Check that it's extending the existing model, not creating new one
        self.assertEqual(supplierinfo._name, "product.supplierinfo")
