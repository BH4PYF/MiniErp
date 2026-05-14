"""
补充测试：覆盖 test_models.py 中未测试的模型。
Profile / BudgetItem / ContractItem / MeasurementItem / SettlementItem
Delivery / OperationLog / MaterialPlan / MaterialPlanItem
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from ..models import (
    Profile, Project,
    Subcontractor, SubcontractCategory, SubcontractList,
    Budget, BudgetItem,
    Contract, ContractItem,
    Measurement, MeasurementItem,
    Settlement, SettlementItem,
    Category, Material, Supplier,
    PurchasePlan, Delivery, OperationLog,
    MaterialPlan, MaterialPlanItem,
)


class ProfileModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='prof_user', password='pass12345')
        cls.profile = Profile.objects.create(user=cls.user, role='management')

    def test_profile_str(self):
        self.assertIn('prof_user', str(self.profile))
        self.assertIn('管理层', str(self.profile))


class BudgetItemModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.project = Project.objects.create(code='BIP001', name='预算测试项目')
        cls.budget = Budget.objects.create(code='BUD001', project=cls.project)
        cls.cat = SubcontractCategory.objects.create(category_code='BCAT', category_name='预算分类')
        cls.sub_list = SubcontractList.objects.create(
            code='BSL001', name='预算清单项',
            category=cls.cat, unit='m²', reference_price=Decimal('100.00')
        )
        cls.item = BudgetItem.objects.create(
            budget=cls.budget,
            item_order=1,
            subcontract_list=cls.sub_list,
            quantity=Decimal('100'),
            unit_price=Decimal('95'),
        )

    def test_budget_item_str(self):
        self.assertIn('BUD001', str(self.item))

    def test_budget_item_total(self):
        self.assertEqual(self.item.total_amount, Decimal('9500'))


class ContractItemModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.project = Project.objects.create(code='CIP001', name='合同测试项目')
        cls.subcontractor = Subcontractor.objects.create(
            code='CSC001', name='合同分包商',
            contact='李工', phone='13900139000', main_type='土建'
        )
        cls.cat = SubcontractCategory.objects.create(category_code='CCAT', category_name='合同分类')
        cls.sub_list = SubcontractList.objects.create(
            code='CSL001', name='合同清单项',
            category=cls.cat, unit='m²', reference_price=Decimal('100.00')
        )
        cls.contract = Contract.objects.create(
            code='CON001', name='测试合同',
            project=cls.project, subcontractor=cls.subcontractor
        )
        cls.item = ContractItem.objects.create(
            contract=cls.contract,
            item_order=1,
            subcontract_list=cls.sub_list,
            quantity=Decimal('100'),
            unit_price=Decimal('95'),
        )

    def test_contract_item_str(self):
        self.assertIn('CON001', str(self.item))

    def test_contract_item_total(self):
        self.assertEqual(self.item.total_amount, Decimal('9500'))


class MeasurementItemModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.project = Project.objects.create(code='MIP001', name='计量测试项目')
        cls.subcontractor = Subcontractor.objects.create(
            code='MSC001', name='计量分包商',
            contact='王工', phone='13900139000', main_type='土建'
        )
        cls.cat = SubcontractCategory.objects.create(category_code='MCAT', category_name='计量分类')
        cls.sub_list = SubcontractList.objects.create(
            code='MSL001', name='计量清单项',
            category=cls.cat, unit='m³', reference_price=Decimal('25.00')
        )
        cls.contract = Contract.objects.create(
            code='MCON001', name='计量合同',
            project=cls.project, subcontractor=cls.subcontractor
        )
        cls.measurement = Measurement.objects.create(
            code='MEAS100',
            contract=cls.contract, project=cls.project,
            subcontractor=cls.subcontractor,
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            previous_value=Decimal('0'),
        )
        cls.item = MeasurementItem.objects.create(
            measurement=cls.measurement,
            item_order=1,
            subcontract_list=cls.sub_list,
            previous_quantity=Decimal('0'),
            current_quantity=Decimal('10'),
            unit_price=Decimal('25'),
        )

    def test_measurement_item_str(self):
        self.assertIn('MEAS100', str(self.item))

    def test_measurement_item_current_value(self):
        self.assertEqual(self.item.current_value, Decimal('250'))


class SettlementItemModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.project = Project.objects.create(code='SIP001', name='结算测试项目')
        cls.subcontractor = Subcontractor.objects.create(
            code='SSC001', name='结算分包商',
            contact='赵工', phone='13900139000', main_type='土建'
        )
        cls.cat = SubcontractCategory.objects.create(category_code='SCAT', category_name='结算分类')
        cls.sub_list = SubcontractList.objects.create(
            code='SSL001', name='结算清单项',
            category=cls.cat, unit='m³', reference_price=Decimal('25.00')
        )
        cls.contract = Contract.objects.create(
            code='SCON001', name='结算合同',
            project=cls.project, subcontractor=cls.subcontractor
        )
        cls.settlement = Settlement.objects.create(
            code='SET100',
            contract=cls.contract, project=cls.project,
            subcontractor=cls.subcontractor,
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            measurement_value=Decimal('10000'),
            deduction_reason='无',
            deduction_amount=Decimal('0'),
        )
        cls.item = SettlementItem.objects.create(
            settlement=cls.settlement,
            item_order=1,
            subcontract_list=cls.sub_list,
            measurement_quantity=Decimal('10'),
            adjusted_quantity=Decimal('10'),
            unit_price=Decimal('25'),
        )

    def test_settlement_item_str(self):
        self.assertIn('SET100', str(self.item))


class DeliveryModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='delivery_op', password='pass12345')
        cls.category = Category.objects.create(name='钢材', code='STEEL')
        cls.material = Material.objects.create(
            name='螺纹钢', code='HRB400', category=cls.category,
            unit='吨', standard_price=Decimal('3800'), spec='Φ25', safety_stock=10,
        )
        cls.supplier = Supplier.objects.create(
            name='供应商A', code='SUPA001',
            contact='张三', phone='13800138000',
        )
        cls.project = Project.objects.create(code='DELP001', name='发货测试项目')
        cls.plan = PurchasePlan.objects.create(
            no='PP001', project=cls.project,
            material=cls.material, quantity=Decimal('100'),
            unit_price=Decimal('3800'), operator=cls.user,
        )
        cls.delivery = Delivery.objects.create(
            no='DL001',
            purchase_plan=cls.plan,
            actual_quantity=Decimal('50'),
            actual_unit_price=Decimal('3700'),
            supplier=cls.supplier,
        )

    def test_delivery_creation(self):
        self.assertEqual(self.delivery.no, 'DL001')
        self.assertEqual(self.delivery.actual_quantity, Decimal('50'))

    def test_delivery_str(self):
        self.assertIn('DL001', str(self.delivery))

    def test_delivery_soft_delete(self):
        self.assertFalse(self.delivery.is_deleted)
        self.delivery.delete()
        self.delivery.refresh_from_db()
        self.assertTrue(self.delivery.is_deleted)
        self.assertIsNotNone(self.delivery.deleted_at)


class OperationLogModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.log = OperationLog.objects.create(
            operator='tester',
            module='Material',
            op_type='create',
            details='创建材料记录',
        )

    def test_operation_log_str(self):
        self.assertIn('tester', str(self.log))
        self.assertIn('创建材料记录', str(self.log))


class MaterialPlanModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='planner_user', password='pass12345')
        cls.project = Project.objects.create(code='MPP001', name='材料计划测试项目')
        cls.material = Material.objects.create(
            name='螺纹钢', code='HRB400',
            category=Category.objects.create(name='钢材', code='STEEL'),
            unit='吨', standard_price=Decimal('3800'), spec='Φ25', safety_stock=10,
        )
        cls.plan = MaterialPlan.objects.create(
            project=cls.project,
            plan_number='MP001',
            created_by=cls.user,
        )
        cls.item = MaterialPlanItem.objects.create(
            material_plan=cls.plan,
            material=cls.material,
            quantity=Decimal('200'),
            unit='吨',
            unit_price=Decimal('3800'),
        )

    def test_material_plan_str(self):
        self.assertIn('MP001', str(self.plan))

    def test_material_plan_item_str(self):
        self.assertIn('螺纹钢', str(self.item))

    def test_material_plan_soft_delete(self):
        self.assertFalse(self.plan.is_deleted)
        self.plan.delete()
        self.plan.refresh_from_db()
        self.assertTrue(self.plan.is_deleted)
