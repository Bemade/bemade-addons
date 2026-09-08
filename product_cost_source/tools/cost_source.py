# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Value objects describing where a cost came from.

These are plain Python, not records. A cost source is a statement about a
moment in time -- "this vendor price, in force until then, covering this much
of the demand" -- and nothing about it wants to be stored.
"""

from dataclasses import dataclass, field


@dataclass
class CostSource:
    """One contribution to a resolved cost.

    :param key: machine name of the source ('stock', 'vendor', ...). Never
        shown to a user; the evidence sentence is what a user reads.
    :param qty: how much of the demand this source covers.
    :param unit_price: price per unit, already in the requested currency.
    :param priced_on: the date this price was last *established*, or None when
        that cannot be determined. None is not a synonym for old -- it means
        unknown, and unknown is never treated as fresh.
    :param in_force_until: end of the agreement backing this price, when there
        is one. None means either no agreement or an open-ended one; see
        ``in_force``.
    :param in_force: whether an agreement covers the requested date. A price
        that is in force is firm regardless of its age.
    """

    key: str
    qty: float
    unit_price: float
    priced_on: object = None
    in_force_until: object = None
    in_force: bool = False

    @property
    def subtotal(self):
        return self.unit_price * self.qty


@dataclass
class CostResolution:
    """A resolved cost together with the evidence for it."""

    unit_cost: float = 0.0
    confidence: str = "unknown"
    sources: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def is_firm(self):
        return self.confidence == "firm"
