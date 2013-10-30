#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import ModelView, Workflow
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Lot', 'Production']
__metaclass__ = PoolMeta


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

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, productions):
        pool = Pool()
        LotCostLine = pool.get('stock.lot.cost_line')

        super(Production, cls).done(productions)

        for production in productions:
            for out_move in production.outputs:
                if out_move.state != 'done' or not out_move.lot:
                    continue
                cost_line_vals = production._get_lot_cost_line_vals(out_move)
                if cost_line_vals:
                    LotCostLine.create(cost_line_vals)

    def _get_lot_cost_line_vals(self, output_move):
        pool = Pool()
        ModelData = pool.get('ir.model.data')

        if not output_move.lot:
            return None

        category_id = ModelData.get_id('stock_lot_cost',
            'cost_category_standard_price')
        return [{
                'lot': output_move.lot.id,
                'category': category_id,
                'unit_price': output_move.unit_price,
                'origin': 'stock.move,%s'%output_move.id
                }]
