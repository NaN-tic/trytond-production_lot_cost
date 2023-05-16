# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.pool import PoolMeta


class BOM(metaclass=PoolMeta):
    __name__ = 'production.bom'
    infrastructure_cost = fields.Numeric('Infrastructure Cost',
        digits=(16, 4),
        help='Infrastructure cost per lot unit')


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    @property
    def infrastructure_cost(self):
        if self.product and self.bom and self.bom.infrastructure_cost:
            return self.bom.infrastructure_cost

    @property
    def output_qty(self):
        quantity = 0.
        for output in self.outputs:
            if output.product == self.product:
                qty = output.quantity
                if self.uom != output.uom:
                    qty = self.uom.compute_qty(output.uom, output.quantity,
                        self.uom, round=False)
                quantity += qty

        return quantity

    def get_cost(self, name):
        cost = super(Production, self).get_cost(name)
        if not self.infrastructure_cost:
            return cost
        for output in self.outputs:
            if not output.lot:
                continue
            if output.product == self.product:
                cost += (Decimal(str(output.internal_quantity)) *
                    self.infrastructure_cost)
        return cost
