#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool
from . import production

def register():
    Pool.register(
        production.BOM,
        production.Lot,
        production.Production,
        production.StockMove,
        module='production_lot_cost', type_='model')
    Pool.register(
        LotCostLine,
        Operation,
        depends=['production_operation'],
        module='production_lot_cost', type_='model')

