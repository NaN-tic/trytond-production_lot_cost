# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from trytond.model import ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['BOM', 'Lot', 'Production']
__metaclass__ = PoolMeta


class BOM:
    __name__ = 'production.bom'
    infrastructure_cost = fields.Numeric('Infrastructure Cost',
        digits=(16, 4),
        help='Infrastructure cost per lot unit')


class Lot:
    __name__ = 'stock.lot'

    def _on_change_product_cost_lines(self):
        pool = Pool()
        Move = pool.get('stock.move')

        context = Transaction().context
        if context.get('from_move'):
            move = Move(context['from_move'])
            if getattr(move, 'production_output', False):
                return None

        return super(Lot, self)._on_change_product_cost_lines()


class Production:
    __name__ = 'production'

    @property
    def infrastructure_cost(self):
        if self.product and self.bom and self.bom.infrastructure_cost:
            return self.bom.infrastructure_cost

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

    @classmethod
    def done(cls, productions):
        pool = Pool()
        LotCostLine = pool.get('stock.lot.cost_line')

        to_create = []
        for production in productions:
            for output in production.outputs:
                if (production.infrastructure_cost and
                        output.product == production.product):
                    output.unit_price += production.infrastructure_cost
                    output.save()
                if not output.lot:
                    continue
                if not output.lot.cost_lines:
                    cost_lines = production._get_output_lot_cost_lines(output,
                        added_infrastructure_cost=True)
                    output.lot.cost_lines = cost_lines
                    output.lot.save()

        LotCostLine.create(to_create)
        super(Production, cls).done(productions)

    def get_output_lot(self, output):
        pool = Pool()
        Config = pool.get('production.configuration')
        config = Config(1)

        lot = super(Production, self).get_output_lot(output)
        cost_lines = self._get_output_lot_cost_lines(output,
            config.output_lot_creation == 'done')
        if cost_lines and not getattr(lot, 'cost_lines', False):
            lot.cost_lines = cost_lines
        return lot

    def _get_output_lot_cost_lines(self, output_move,
            added_infrastructure_cost=False):
        '''
        Return a list of unpersistent stock.lot.cost_line instances to be
        writen in cost_lines field of output_move's lot (the returned lines
        doesn't have the lot's field)
        '''
        pool = Pool()
        ModelData = pool.get('ir.model.data')

        inputs_category_id = ModelData.get_id('production_lot_cost',
            'cost_category_inputs_cost')
        infrastructure_category_id = ModelData.get_id('production_lot_cost',
            'cost_category_infrastructure_cost')

        unit_price = output_move.unit_price
        #Infrastructure cost already added before so we must rest it.
        if (added_infrastructure_cost and self.infrastructure_cost and
                output_move.product == self.product):
            unit_price -= self.infrastructure_cost
        res = [
            self._get_output_lot_cost_line(output_move, inputs_category_id,
                unit_price),
            ]

        if self.product == output_move.product and self.infrastructure_cost:
            infrastructure_cost = self._get_output_lot_cost_line(output_move,
                infrastructure_category_id, self.infrastructure_cost)
            res.append(infrastructure_cost)
        return res

    def _get_output_lot_cost_line(self, output_move, category_id, cost):
        pool = Pool()
        LotCostLine = pool.get('stock.lot.cost_line')
        return LotCostLine(
            category=category_id,
            unit_price=cost,
            origin=str(output_move)
            )
