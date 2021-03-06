# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.modules.product import price_digits

__all__ = ['BOM', 'Lot', 'Production', 'StockMove']


class BOM(metaclass=PoolMeta):
    __name__ = 'production.bom'
    infrastructure_cost = fields.Numeric('Infrastructure Cost',
        digits=(16, 4),
        help='Infrastructure cost per lot unit')


class Lot(metaclass=PoolMeta):
    __name__ = 'stock.lot'

    def _on_change_product_cost_lines(self):
        pool = Pool()
        Move = pool.get('stock.move')

        context = Transaction().context
        if context.get('from_move'):
            move = Move(context['from_move'])
            if getattr(move, 'production_output', False):
                return {}

        return super(Lot, self)._on_change_product_cost_lines()


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

    #def explode_bom(self):
        #super(Production, self).explode_bom()
        #outputs = self.outputs
        #for move in outputs:
            #if self.infrastructure_cost and move.product == self.product:
                #move.unit_price += self.infrastructure_cost

    @classmethod
    def set_cost(cls, productions):
        Lot = Pool().get('stock.lot')

        super(Production, cls).set_cost(productions)

        to_save = []
        to_check = []
        for production in productions:
            for output in production.outputs:
                if not output.lot:
                    continue
                if not output.lot.cost_lines:
                    cost_lines = output._get_production_output_lot_cost_lines()
                    output.lot.cost_lines = cost_lines
                    to_save.append(output.lot)
                to_check.append((output, output.lot))
        if to_save:
            Lot.save(to_save)
        if to_check:
            for move, lot in to_check:
                move.check_lot_cost(lot)


class StockMove(metaclass=PoolMeta):
    __name__ = 'stock.move'

    def check_lot_cost(self, lot):
        '''
        If production output quantity is changed manually, it cannot be
        computed the lot cost, so lot must be created manually.
        '''
        production = self.production_output

        if self.uom != production.uom:
            unit_price = self.uom.compute_price(self.uom, self.unit_price,
                production.uom)
        else:
            unit_price = self.unit_price

        digits = price_digits[1]
        cost_price = Decimal(lot.cost_price).quantize(
            Decimal(str(10 ** -digits)))
        unit_price = Decimal(unit_price).quantize(
            Decimal(str(10 ** -digits)))

        if unit_price != cost_price:
            raise UserError(gettext('production_lot_cost.msg_uneven_costs',
                    move=self.rec_name,
                    move_unit_price=self.unit_price,
                    lot=self.lot,
                    lot_unit_price=lot.cost_price,
                    ))

    def get_production_output_lot(self):
        lot = super(StockMove, self).get_production_output_lot()
        if lot:
            cost_lines = self._get_production_output_lot_cost_lines()
            if cost_lines and not getattr(lot, 'cost_lines', False):
                lot.cost_lines = cost_lines
        return lot

    def _get_production_output_lot_cost_lines(self):
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

        # Unit price of cost_line should not include infrastructure_cost but
        # as production.cost computed method is overriden and it includes this
        # cost, here we must compute the original production cost again
        production = self.production_output
        cost = Decimal(0)
        for input_ in production.inputs:
            if input_.cost_price is not None:
                cost_price = input_.cost_price
            else:
                cost_price = input_.product.cost_price
            cost += (Decimal(str(input_.internal_quantity)) * cost_price)

        factor = 1
        res = []
        if production.bom:
            factor = production.bom.compute_factor(production.product,
                production.quantity or 0, production.uom)
            for output in production.bom and production.bom.outputs or []:
                quantity = output.compute_quantity(factor)
                if output.product == self.product and quantity:
                    res.append(
                        self._get_production_output_lot_cost_line(
                            inputs_category_id,
                            Decimal(cost / Decimal(str(quantity))))
                        )

        elif (self.product == production.product and self.quantity):
            quantity = production.output_qty
            if quantity:
                res.append(
                    self._get_production_output_lot_cost_line(
                        inputs_category_id,
                        Decimal(cost / Decimal(str(quantity))))
                    )

        if (self.product == production.product and
                production.infrastructure_cost):
            infrastructure_cost = self._get_production_output_lot_cost_line(
                infrastructure_category_id, production.infrastructure_cost)
            res.append(infrastructure_cost)

        return res

    def _get_production_output_lot_cost_line(self, category_id, cost):
        pool = Pool()
        LotCostLine = pool.get('stock.lot.cost_line')
        return LotCostLine(
            category=category_id,
            unit_price=cost,
            origin=str(self)
            )
