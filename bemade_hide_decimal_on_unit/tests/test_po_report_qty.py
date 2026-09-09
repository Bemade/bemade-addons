# -*- coding: utf-8 -*-
import re

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPoReportQty(TransactionCase):
    """The purchase report override must print the line-UoM quantity
    (``product_qty``), not the UoM-converted ``product_uom_qty``.

    Acceptance:
      - AC#1: a line at 100.50 in its line UoM prints 100.50, not the
        converted 10.05 (the reported bug).
      - AC#2: a whole-number line (5.0) prints "5", not "5.0" (hide-decimals
        branch still fires on the corrected field).
      - AC#4: both the PO document and the quotation document templates are
        corrected — both are rendered and asserted here.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Uom = cls.env["uom.uom"]
        Product = cls.env["product.product"]

        # One UoM category with a reference unit ("line hours") and a unit that
        # is 10x bigger ("product big-hours", factor 0.1). The PO line is entered
        # in the reference unit; the product's default UoM is the bigger one, so
        # product_uom._compute_quantity(product_qty, product.uom_id) converts and
        # 100.50 (line) -> 10.05 (product UoM): exactly the reported bug.
        category = cls.env["uom.category"].create({"name": "Test Time 3072"})
        cls.uom_line = Uom.create({
            "name": "Test Hours 3072",
            "category_id": category.id,
            "uom_type": "reference",
            "factor": 1.0,
        })
        cls.uom_product = Uom.create({
            "name": "Test BigHours 3072",
            "category_id": category.id,
            "uom_type": "bigger",
            "factor": 0.1,  # 1 big-hour = 10 reference hours
        })

        cls.product = Product.create({
            "name": "FEE-ENG 3072",
            "type": "service",
            "uom_id": cls.uom_product.id,
            "uom_po_id": cls.uom_product.id,
            "purchase_method": "purchase",
        })
        cls.vendor = cls.env["res.partner"].create({"name": "Vendor 3072"})

        cls.order = cls.env["purchase.order"].create({
            "partner_id": cls.vendor.id,
            "order_line": [
                (0, 0, {
                    "product_id": cls.product.id,
                    "name": "FEE-ENG",
                    # 100.50 in the LINE UoM (reference hours)
                    "product_qty": 100.50,
                    "product_uom": cls.uom_line.id,
                    "price_unit": 100.0,
                }),
                (0, 0, {
                    "product_id": cls.product.id,
                    "name": "FEE-ENG whole",
                    # 5.0 whole -> hide-decimals branch
                    "product_qty": 5.0,
                    "product_uom": cls.uom_line.id,
                    "price_unit": 100.0,
                }),
            ],
        })

        cls.fractional_line = cls.order.order_line[0]
        cls.whole_line = cls.order.order_line[1]

    def _quantity_cells(self, html):
        """Extract the text of every <td name="td_quantity"> cell."""
        html = html.decode() if isinstance(html, bytes) else html
        cells = re.findall(
            r'<td[^>]*name="td_quantity"[^>]*>(.*?)</td>', html, re.DOTALL
        )
        # strip tags + collapse whitespace per cell
        out = []
        for c in cells:
            text = re.sub(r"<[^>]+>", " ", c)
            out.append(re.sub(r"\s+", " ", text).strip())
        return out

    def _sanity(self):
        # Guard the test premise: product_uom_qty really differs from product_qty
        # by the 10x ratio, so a regression to product_uom_qty would print 10.05.
        self.assertEqual(self.fractional_line.product_qty, 100.50)
        self.assertAlmostEqual(
            self.fractional_line.product_uom_qty, 10.05, places=2,
            msg="setup must create a real UoM conversion (100.50 -> 10.05)",
        )

    def _assert_quantities(self, cells, label):
        # AC#1: fractional line prints the LINE qty (product_qty == 100.50),
        # not the UoM-converted product_uom_qty (== 10.05, the reported bug).
        # The non-whole branch renders the raw float via t-esc, so 100.50 prints
        # as "100.5" (Python float str drops the trailing zero) -- this matches
        # the module's pre-existing raw-t-esc behaviour; the load-bearing check
        # is that it is the line value (100.5...), never the converted 10.05.
        joined = " ".join(cells)
        self.assertTrue(
            any(c.startswith("100.5") for c in cells),
            "%s: expected line product_qty 100.5 in the quantity cells, got %r"
            % (label, cells),
        )
        self.assertNotIn(
            "10.05", joined,
            "%s: converted product_uom_qty 10.05 leaked into the PDF (the bug) %r"
            % (label, cells),
        )
        # AC#2: whole-number line prints "5" with no trailing decimals.
        self.assertTrue(
            any(re.search(r"\b5\b", c) and "5.0" not in c for c in cells),
            "%s: whole qty 5.0 must render as '5' (hide-decimals branch), got %r"
            % (label, cells),
        )

    def test_po_document_prints_line_product_qty(self):
        """AC#1 / AC#2 on the purchase order document template."""
        self._sanity()
        report = self.env.ref("purchase.action_report_purchase_order")
        html, _ = report._render_qweb_html(
            "purchase.report_purchaseorder", self.order.ids
        )
        cells = self._quantity_cells(html)
        self.assertTrue(cells, "no td_quantity cells found in PO document render")
        self._assert_quantities(cells, "PO document")

    def test_quotation_document_prints_line_product_qty(self):
        """AC#4: the quotation document gets the identical field correction."""
        self._sanity()
        report = self.env.ref("purchase.report_purchase_quotation")
        html, _ = report._render_qweb_html(
            "purchase.report_purchasequotation", self.order.ids
        )
        cells = self._quantity_cells(html)
        self.assertTrue(
            cells, "no td_quantity cells found in quotation document render"
        )
        self._assert_quantities(cells, "Quotation document")
