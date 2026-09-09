# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import Command

from odoo.addons.base.tests.common import BaseCommon


class BomVariantRuleCommon(BaseCommon):
    """Shared fixture: a two-attribute configurable template.

    Deliberately domain-neutral. ``Size`` values carry numeric parameters
    (``volume`` and ``height``); ``Count`` values carry ``trains``. That is
    enough to exercise merging, arithmetic and conflict handling without
    importing anything about water treatment.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Attribute = cls.env["product.attribute"]
        Value = cls.env["product.attribute.value"]

        cls.attr_size = Attribute.create(
            {"name": "Size", "create_variant": "dynamic"}
        )
        cls.size_small = Value.create(
            {
                "name": "Small",
                "attribute_id": cls.attr_size.id,
                "param_ids": [
                    Command.create({"name": "volume", "value": 1.0}),
                    Command.create({"name": "height", "value": 48.0}),
                ],
            }
        )
        cls.size_large = Value.create(
            {
                "name": "Large",
                "attribute_id": cls.attr_size.id,
                "param_ids": [
                    Command.create({"name": "volume", "value": 1.5}),
                    Command.create({"name": "height", "value": 54.0}),
                ],
            }
        )

        cls.attr_count = Attribute.create(
            {"name": "Count", "create_variant": "dynamic"}
        )
        cls.count_single = Value.create(
            {
                "name": "Single",
                "attribute_id": cls.attr_count.id,
                "param_ids": [Command.create({"name": "trains", "value": 1.0})],
            }
        )
        cls.count_twin = Value.create(
            {
                "name": "Twin",
                "attribute_id": cls.attr_count.id,
                "param_ids": [Command.create({"name": "trains", "value": 2.0})],
            }
        )

        cls.template = cls.env["product.template"].create(
            {
                "name": "Configurable Assembly",
                "type": "consu",
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": cls.attr_size.id,
                            "value_ids": [
                                Command.set(
                                    [cls.size_small.id, cls.size_large.id]
                                )
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "attribute_id": cls.attr_count.id,
                            "value_ids": [
                                Command.set(
                                    [cls.count_single.id, cls.count_twin.id]
                                )
                            ],
                        }
                    ),
                ],
            }
        )

    @classmethod
    def _variant(cls, size_value, count_value):
        """Materialise the variant carrying the two given attribute values."""
        ptavs = cls.env["product.template.attribute.value"].search(
            [
                ("product_tmpl_id", "=", cls.template.id),
                (
                    "product_attribute_value_id",
                    "in",
                    [size_value.id, count_value.id],
                ),
            ]
        )
        return cls.template._create_product_variant(ptavs)
