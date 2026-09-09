# Copyright (C) 2024 Bemade Inc. (<https://www.bemade.org>).
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
"""
Test: TestFormWidgetTour
========================

Exercises the SO form's partner_invoice_id and partner_shipping_id Many2one
widgets via a JS tour to ensure the view XML context attributes are correct and
the ranked/favorite addresses actually appear first in the dropdown.

This is the strongest possible coverage: a typo in the view xpath, a wrong
context attribute, or a broken name_search override would all cause the JS
assertions to fail here, while direct name_search unit tests would not catch
them.

AC (from tour assertions):
- The favorite invoice contact (C_inv2) is the first option in the
  partner_invoice_id dropdown on a new SO for TourCo.
- The most-used delivery contact (C_ship1) is the first option in the
  partner_shipping_id dropdown on that same SO.
"""
import odoo.tests
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestFormWidgetTour(odoo.tests.HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Grant the admin user access to the invoice/delivery address fields
        # on the SO form (gated by account.group_delivery_invoice_address).
        group = cls.env.ref("account.group_delivery_invoice_address")
        cls.env.ref("base.user_admin").groups_id |= group

        Partner = cls.env["res.partner"]

        # Company
        cls.tour_company = Partner.create(
            {"name": "TourCo", "is_company": True}
        )

        # Two invoice-type contacts; TourInv2 will be marked as favorite
        cls.tour_inv1 = Partner.create(
            {
                "name": "TourInv1",
                "parent_id": cls.tour_company.id,
                "type": "invoice",
            }
        )
        cls.tour_inv2 = Partner.create(
            {
                "name": "TourInv2",
                "parent_id": cls.tour_company.id,
                "type": "invoice",
                "is_favorite_invoice": True,
            }
        )

        # One delivery-type contact; will be ranked top by usage
        cls.tour_ship1 = Partner.create(
            {
                "name": "TourShip1",
                "parent_id": cls.tour_company.id,
                "type": "delivery",
            }
        )

        # Create 3 confirmed SOs using TourShip1 as the shipping address so
        # it ranks first in the delivery dropdown via usage-based ranking.
        SaleOrder = cls.env["sale.order"]
        for _ in range(3):
            so = SaleOrder.create(
                {
                    "partner_id": cls.tour_company.id,
                    "partner_invoice_id": cls.tour_inv1.id,
                    "partner_shipping_id": cls.tour_ship1.id,
                }
            )
            so.action_confirm()

    def test_tour_selects_favorite_first(self):
        """JS tour asserts favorite invoice and top-ranked delivery appear
        first in their respective Many2one dropdowns on the SO form."""
        self.start_tour(
            "/odoo/sales",
            "partner_address_ranking_tour",
            login="admin",
        )
