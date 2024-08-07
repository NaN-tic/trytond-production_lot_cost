import unittest
from decimal import Decimal

from proteus import Model
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Activate production_output_lot and production_lot_cost
        config = activate_modules(
            ['production_output_lot', 'production_lot_cost'])

        # Create company
        _ = create_company()
        company = get_company()

        # Reload the context
        User = Model.get('res.user')
        config._context = User.get_preferences(True, config.context)

        # Configuration production location
        Location = Model.get('stock.location')
        warehouse, = Location.find([('code', '=', 'WH')])
        production_location, = Location.find([('code', '=', 'PROD')])
        warehouse.production_location = production_location
        warehouse.save()

        # Create lot sequence type and produced lots sequence
        SequenceType = Model.get('ir.sequence.type')
        sequence_type, = SequenceType.find([('name', '=', 'Stock Lot')])
        Sequence = Model.get('ir.sequence')
        lot_sequence = Sequence(name='Produced Lots',
                                sequence_type=sequence_type,
                                company=company)
        lot_sequence.save()

        # Create product with lots required
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        Product = Model.get('product.product')
        product = Product()
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'goods'
        template.producible = True
        template.list_price = Decimal(30)
        template.lot_required = [
            'supplier', 'customer', 'lost_found', 'storage', 'production'
        ]
        template.save()
        product, = template.products
        product.cost_price = Decimal(20)
        product.save()

        # Create Components
        component1 = Product()
        template1 = ProductTemplate()
        template1.name = 'component 1'
        template1.default_uom = unit
        template1.type = 'goods'
        template1.list_price = Decimal(5)
        template1.save()
        component1, = template1.products
        component1.cost_price = Decimal(1)
        component1.save()
        meter, = ProductUom.find([('name', '=', 'Meter')])
        centimeter, = ProductUom.find([('symbol', '=', 'cm')])
        component2 = Product()
        template2 = ProductTemplate()
        template2.name = 'component 2'
        template2.default_uom = meter
        template2.type = 'goods'
        template2.list_price = Decimal(7)
        template2.save()
        component2, = template2.products
        component2.cost_price = Decimal(5)
        component2.save()

        # Create Bill of Material with infrastructure cost
        BOM = Model.get('production.bom')
        BOMInput = Model.get('production.bom.input')
        BOMOutput = Model.get('production.bom.output')
        bom = BOM(name='product')
        input1 = BOMInput()
        bom.inputs.append(input1)
        input1.product = component1
        input1.quantity = 5
        input2 = BOMInput()
        bom.inputs.append(input2)
        input2.product = component2
        input2.quantity = 150
        input2.uom = centimeter
        output = BOMOutput()
        bom.outputs.append(output)
        output.product = product
        output.quantity = 1
        bom.infrastructure_cost = Decimal('1.0')
        bom.save()
        ProductBom = Model.get('product.product-production.bom')
        product.boms.append(ProductBom(bom=bom))
        product.save()

        # Create an Inventory
        Inventory = Model.get('stock.inventory')
        InventoryLine = Model.get('stock.inventory.line')
        storage, = Location.find([
            ('code', '=', 'STO'),
        ])
        inventory = Inventory()
        inventory.location = storage
        inventory_line1 = InventoryLine()
        inventory.lines.append(inventory_line1)
        inventory_line1.product = component1
        inventory_line1.quantity = 20
        inventory_line2 = InventoryLine()
        inventory.lines.append(inventory_line2)
        inventory_line2.product = component2
        inventory_line2.quantity = 10
        inventory.save()
        inventory.click('confirm')
        self.assertEqual(inventory.state, 'done')

        # Configure production to automatically create lots on running state
        ProductionConfig = Model.get('production.configuration')
        production_config = ProductionConfig(1)
        production_config.output_lot_creation = 'running'
        production_config.output_lot_sequence = lot_sequence
        production_config.save()

        # Make a production with infrastructure cost and lots automatically created when

        # production is Running
        Production = Model.get('production')
        production = Production()
        production.product = product
        production.bom = bom
        production.quantity = 2
        self.assertEqual(
            sorted([i.quantity for i in production.inputs]), [10, 300])
        output, = production.outputs
        self.assertEqual(output.quantity, 2)
        production.save()
        production.click('wait')
        self.assertEqual(production.state, 'waiting')
        production.click('assign_try')
        self.assertEqual(all(i.state == 'assigned' for i in production.inputs),
                         True)
        production.click('run')
        self.assertEqual(all(i.state == 'done' for i in production.inputs),
                         True)
        output, = production.outputs
        self.assertNotEqual(output.lot, None)
        production.click('done')
        output, = production.outputs
        self.assertEqual(output.state, 'done')
        self.assertEqual(production.cost, Decimal('27'))
        self.assertEqual(output.unit_price, Decimal('13.5000'))
        self.assertEqual(output.lot.cost_price, Decimal('13.5'))

        # Configure production to automatically create lots on done state
        production_config.output_lot_creation = 'done'
        production_config.save()

        # Make a production with infrastructure cost and lots automatically created when

        # production is done
        production = Production()
        production.product = product
        production.bom = bom
        production.quantity = 2
        self.assertEqual(
            sorted([i.quantity for i in production.inputs]), [10, 300])
        output, = production.outputs
        self.assertEqual(output.quantity, 2)
        production.save()
        production.click('wait')
        self.assertEqual(production.state, 'waiting')
        production.click('assign_try')
        self.assertEqual(all(i.state == 'assigned' for i in production.inputs),
                         True)
        production.click('run')
        self.assertEqual(all(i.state == 'done' for i in production.inputs),
                         True)
        output, = production.outputs
        output.lot
        production.click('done')
        output, = production.outputs
        self.assertEqual(output.state, 'done')
        self.assertNotEqual(output.lot, None)
        self.assertEqual(production.cost, Decimal('27'))
        self.assertEqual(output.unit_price, Decimal('13.5000'))
        self.assertEqual(output.lot.cost_price, Decimal('13.5'))
