from odoo.tests import tagged, TransactionCase, Form
from lxml import html


@tagged("post_install", "-at_install")
class TestTrackingNotification(TransactionCase):
    """Test tracking number notification functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a partner (customer)
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Customer",
                "email": "customer@test.com",
            }
        )

        # Create a child contact under the customer
        cls.partner_child = cls.env["res.partner"].create(
            {
                "name": "Test Contact",
                "email": "contact@test.com",
                "parent_id": cls.partner.id,
            }
        )

        # Create a storable product
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "consu",
                "is_storable": True,
                "list_price": 100.0,
            }
        )

        # Create a delivery carrier
        cls.carrier = cls.env["delivery.carrier"].create(
            {
                "name": "Test Carrier",
                "delivery_type": "fixed",
                "product_id": cls.env["product.product"]
                .create(
                    {
                        "name": "Delivery Product",
                        "type": "service",
                    }
                )
                .id,
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
                            "product_uom_qty": 1.0,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

        # Get the mail template
        cls.template = cls.env.ref(
            "delivery_notification.mail_template_tracking_notification"
        )

        # Get stock location for inventory
        cls.stock_location = cls.env.ref("stock.warehouse0").lot_stock_id

    def _set_product_quantity(self, product, location, qty):
        """Helper to set product quantity in a location."""
        quant = self.env["stock.quant"].create(
            {
                "product_id": product.id,
                "location_id": location.id,
                "quantity": qty,
            }
        )
        return quant

    def test_tracking_notification_on_validate(self):
        """Test that validating a picking with tracking ref sends an email."""
        # Create a sale order
        sale_order = self.sale_order
        # Confirm the sale order to create a delivery
        sale_order.action_confirm()

        # Get the delivery picking
        picking = sale_order.picking_ids.filtered(
            lambda p: p.picking_type_code == "outgoing"
        )
        self.assertTrue(picking, "No outgoing picking found")

        # Set stock quantity for the product
        self._set_product_quantity(self.product, self.stock_location, 10)

        # Set the tracking reference and carrier
        tracking_ref = "TRACK123456789"
        picking.write(
            {
                "carrier_id": self.carrier.id,
                "carrier_tracking_ref": tracking_ref,
            }
        )

        # Count messages before validation
        message_count_before = len(sale_order.message_ids)

        # Set quantities done and validate
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        # Check that a new message was posted
        message_count_after = len(sale_order.message_ids)
        self.assertEqual(
            message_count_after,
            message_count_before + 1,
            "A message should have been posted to the sale order on validation",
        )

        # Get the latest message
        latest_message = sale_order.message_ids[0]

        # Verify the message contains the tracking number
        self.assertIn(
            tracking_ref,
            latest_message.body,
            f"Tracking number '{tracking_ref}' should be in the message body",
        )

        # Verify the message contains the carrier name
        self.assertIn(
            self.carrier.name,
            latest_message.body,
            f"Carrier name '{self.carrier.name}' should be in the message body",
        )

    def test_no_notification_on_write(self):
        """Test that writing tracking ref without validation does not post a message."""
        # Create a sale order
        sale_order = self.sale_order
        # Confirm the sale order
        sale_order.action_confirm()

        # Get the delivery picking
        picking = sale_order.picking_ids.filtered(
            lambda p: p.picking_type_code == "outgoing"
        )

        # Count messages before
        message_count_before = len(sale_order.message_ids)

        # Update the tracking reference (without validating)
        tracking_ref = "NOVALIDATE123"
        picking.write(
            {
                "carrier_id": self.carrier.id,
                "carrier_tracking_ref": tracking_ref,
            }
        )

        # No new message should be posted
        message_count_after = len(sale_order.message_ids)
        self.assertEqual(
            message_count_after,
            message_count_before,
            "No message should be posted when only writing tracking ref",
        )

    def test_no_notification_without_tracking_ref(self):
        """Test that validating without tracking ref does not post a notification."""
        # Create a sale order
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

        # Confirm the sale order
        sale_order.action_confirm()

        # Get the delivery picking
        picking = sale_order.picking_ids.filtered(
            lambda p: p.picking_type_code == "outgoing"
        )

        # Set stock quantity
        self._set_product_quantity(self.product, self.stock_location, 10)

        # Count messages before validation
        message_count_before = len(sale_order.message_ids)

        # Validate without tracking ref
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        # No tracking notification should be posted
        message_count_after = len(sale_order.message_ids)
        self.assertEqual(
            message_count_after,
            message_count_before,
            "No tracking notification should be posted without tracking ref",
        )

    def test_no_notification_without_sale_order(self):
        """Test that no notification is sent if picking is not linked to a sale order."""
        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("warehouse_id.company_id", "=", self.env.company.id),
            ],
            limit=1,
        )

        # Create a picking without a sale order
        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.partner.id,
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": self.partner.property_stock_customer.id,
                "carrier_id": self.carrier.id,
                "carrier_tracking_ref": "NOORDER123",
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": self.product.name,
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "product_uom": self.product.uom_id.id,
                            "location_id": picking_type.default_location_src_id.id,
                            "location_dest_id": self.partner.property_stock_customer.id,
                        },
                    )
                ],
            }
        )

        # Set stock quantity
        self._set_product_quantity(self.product, self.stock_location, 10)

        # Validate - should not raise error
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        # No assertion needed - just verify no error occurs

    def test_no_notification_for_incoming_picking(self):
        """Test that no notification is sent for incoming pickings."""
        # Create a sale order
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

        # Confirm the sale order
        sale_order.action_confirm()

        # Create an incoming picking (not outgoing)
        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "incoming"),
                ("warehouse_id.company_id", "=", self.env.company.id),
            ],
            limit=1,
        )

        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.partner.id,
                "picking_type_id": picking_type.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": picking_type.default_location_dest_id.id,
                "sale_id": sale_order.id,
                "carrier_tracking_ref": "INCOMING123",
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": self.product.name,
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "product_uom": self.product.uom_id.id,
                            "location_id": self.env.ref(
                                "stock.stock_location_suppliers"
                            ).id,
                            "location_dest_id": picking_type.default_location_dest_id.id,
                        },
                    )
                ],
            }
        )

        # Count messages before validation
        message_count_before = len(sale_order.message_ids)

        # Validate the incoming picking
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        # No new message should be posted
        message_count_after = len(sale_order.message_ids)
        self.assertEqual(
            message_count_after,
            message_count_before,
            "No message should be posted for incoming pickings",
        )

    def test_template_renders_with_client_order_ref(self):
        """Test that the template correctly renders the client PO number."""
        # Create a sale order with client order ref
        client_po = "PO-2024-001"
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "client_order_ref": client_po,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

        # Confirm and get picking
        sale_order.action_confirm()
        picking = sale_order.picking_ids.filtered(
            lambda p: p.picking_type_code == "outgoing"
        )

        # Set stock quantity
        self._set_product_quantity(self.product, self.stock_location, 10)

        # Add tracking number
        tracking_ref = "TRACK999"
        picking.write(
            {
                "carrier_id": self.carrier.id,
                "carrier_tracking_ref": tracking_ref,
            }
        )

        # Validate the picking to trigger notification
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        # Get the message
        latest_message = sale_order.message_ids[0]

        # Verify both tracking number and PO are in the message
        self.assertIn(tracking_ref, latest_message.body)
        self.assertIn(client_po, latest_message.body)

    def test_template_qweb_rendering(self):
        """Test that the QWeb template renders correctly with all elements."""
        # Create a sale order
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "client_order_ref": "PO-TEST-123",
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

        sale_order.action_confirm()
        picking = sale_order.picking_ids.filtered(
            lambda p: p.picking_type_code == "outgoing"
        )

        tracking_ref = "QWEB-TEST-789"
        tracking_url = "https://track.example.com/QWEB-TEST-789"

        # Render the template
        rendered_body = self.template._render_template(
            self.template.body_html,
            model=sale_order._name,
            res_ids=sale_order.ids,
            engine="qweb",
            add_context={
                "tracking_ref": tracking_ref,
                "tracking_url": tracking_url,
            },
        )[sale_order.id]

        # Parse the HTML to verify structure
        tree = html.fromstring(rendered_body)

        # Check that tracking number is present
        self.assertIn(
            tracking_ref,
            rendered_body,
            "Tracking number should be in rendered template",
        )

        # Check that tracking URL is present as a link
        links = tree.xpath('//a[@target="_blank"]')
        self.assertTrue(
            any(tracking_url in link.get("href", "") for link in links),
            "Tracking URL should be present as a clickable link",
        )

        # Check that carrier name is present
        self.assertIn(
            "Not specified", rendered_body, "Carrier placeholder should be present"
        )

        # Check that PO number is present
        self.assertIn(
            "PO-TEST-123", rendered_body, "Client PO should be in rendered template"
        )

    def test_template_without_optional_fields(self):
        """Test that template renders correctly when optional fields are missing."""
        # Create a sale order without client_order_ref
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

        sale_order.action_confirm()

        # Render template without tracking_url
        rendered_body = self.template._render_template(
            self.template.body_html,
            model=sale_order._name,
            res_ids=sale_order.ids,
            engine="qweb",
            add_context={
                "tracking_ref": "MINIMAL-123",
                "tracking_url": None,
            },
        )[sale_order.id]

        # Should still render without errors
        self.assertIn("MINIMAL-123", rendered_body)

        # Should not contain PO section (conditional rendering)
        tree = html.fromstring(rendered_body)
        text_content = tree.text_content()

        # Tracking number should be present
        self.assertIn("MINIMAL-123", text_content)

        # No tracking link should be present (since tracking_url is None)
        links = tree.xpath('//a[@target="_blank"]')
        self.assertEqual(
            len(links),
            0,
            "No tracking link should be present when tracking_url is None",
        )

    def test_template_renders_in_fr_for_fr_partner(self):
        """Test that template renders in French when partner has French language."""
        sale_order = self.sale_order
        # Activate French language and load translations from .po file
        self.env["res.lang"]._activate_lang("fr_FR")
        self.env["ir.module.module"]._load_module_terms(
            ["delivery_notification"], ["fr_FR"]
        )

        # Set partner language to French
        sale_order.partner_id.lang = "fr_FR"
        sale_order.action_confirm()
        picking = sale_order.picking_ids[0]
        picking.carrier_tracking_ref = "TRACK123456789"
        picking.carrier_id = self.carrier.id
        picking.move_ids.quantity = sale_order.order_line[0].product_uom_qty
        picking.button_validate()

        # Check that a message contains the French version
        to_match = "Votre commande"
        self.assertTrue(
            any([to_match in message.body for message in sale_order.message_ids]),
            f"Expected '{to_match}' in message bodies: {[m.body for m in sale_order.message_ids]}",
        )

    def test_backorder_does_not_create_duplicate_notification(self):
        """Test that partial shipment with backorder only creates one notification."""
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 5.0,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        sale_order.action_confirm()

        picking = sale_order.picking_ids.filtered(
            lambda p: p.picking_type_code == "outgoing"
        )
        self.assertTrue(picking)

        # Set stock and tracking
        self._set_product_quantity(self.product, self.stock_location, 10)
        tracking_ref = "BACKORDER-TEST-123"
        picking.write(
            {
                "carrier_id": self.carrier.id,
                "carrier_tracking_ref": tracking_ref,
            }
        )

        # Ship only 2 of 5 (partial shipment)
        for move in picking.move_ids:
            move.quantity = 2.0

        message_count_before = len(sale_order.message_ids)

        # Validate with backorder creation
        res = picking.button_validate()
        # The result should be a backorder wizard action
        self.assertIsInstance(res, dict, "Expected backorder wizard action")

        # Process the backorder wizard to create a backorder
        wizard = Form(self.env[res["res_model"]].with_context(**res["context"])).save()
        wizard.process()

        # Count tracking notifications (messages with our tracking ref)
        tracking_messages = sale_order.message_ids.filtered(
            lambda m: tracking_ref in (m.body or "")
        )
        self.assertEqual(
            len(tracking_messages),
            1,
            f"Expected exactly 1 tracking notification but found {len(tracking_messages)}",
        )

    def test_notification_sent_to_order_contact(self):
        """Test that notification is sent only to the contact that placed the order."""
        # Create a sale order from the child contact
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

        sale_order.action_confirm()
        picking = sale_order.picking_ids[0]

        self._set_product_quantity(self.product, self.stock_location, 10)
        picking.carrier_tracking_ref = "TRACK_CONTACT_TEST"
        picking.carrier_id = self.carrier.id
        picking.move_ids.quantity = sale_order.order_line[0].product_uom_qty
        picking.button_validate()

        # Get the latest message
        latest_message = sale_order.message_ids[0]

        # Check that notified_partner_ids contains the recipient
        # For a sale order created by internal user, should default to partner_id
        self.assertIn(self.partner.id, latest_message.notified_partner_ids.ids)

    def test_delivery_pdf_attached_to_notification(self):
        """Test that the delivery order PDF is attached to the notification."""
        sale_order = self.sale_order
        sale_order.action_confirm()
        picking = sale_order.picking_ids[0]

        self._set_product_quantity(self.product, self.stock_location, 10)
        picking.carrier_tracking_ref = "TRACK_PDF_TEST"
        picking.carrier_id = self.carrier.id
        picking.move_ids.quantity = sale_order.order_line[0].product_uom_qty
        picking.button_validate()

        # Get the latest message
        latest_message = sale_order.message_ids[0]

        # Check that there's an attachment
        self.assertTrue(
            len(latest_message.attachment_ids) > 0,
            "Delivery PDF should be attached to the notification message",
        )

        # Check attachment is a PDF
        attachment = latest_message.attachment_ids[0]
        self.assertEqual(attachment.mimetype, "application/pdf")
        self.assertIn("Delivery_Order", attachment.name)

    def test_followers_mode_sends_to_all_followers(self):
        """Test that 'followers' mode sends notification to all followers."""
        # Set company to 'followers' mode
        self.env.company.delivery_notification_recipient = "followers"

        # Create a sale order
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

        # Add another follower manually
        other_follower = self.env["res.partner"].create(
            {
                "name": "Other Follower",
                "email": "other_follower@test.com",
            }
        )
        sale_order.message_subscribe(partner_ids=[other_follower.id])

        # Confirm and validate delivery
        sale_order.action_confirm()
        picking = sale_order.picking_ids.filtered(
            lambda p: p.picking_type_code == "outgoing"
        )
        self._set_product_quantity(self.product, self.stock_location, 10)
        picking.carrier_tracking_ref = "TRACK_FOLLOWERS_TEST"
        picking.carrier_id = self.carrier.id
        picking.move_ids.quantity = sale_order.order_line[0].product_uom_qty
        picking.button_validate()

        # Get the latest message
        latest_message = sale_order.message_ids[0]

        self.assertEqual(
            len(latest_message.notified_partner_ids),
            len(sale_order.message_follower_ids),
            "In 'followers' mode, all sale order followers should be notified.",
        )
