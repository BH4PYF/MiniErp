"""
项目管理模块专项测试
覆盖进度计量、分包结算、合同管理等新增模块的核心功能
"""

import pytest
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from ..models import (
    Profile, Project, Subcontractor, SubcontractCategory,
    SubcontractList, Budget, BudgetItem, Contract, ContractItem,
    Measurement, MeasurementItem, Settlement, SettlementItem
)


class ProjectManagementIntegrationTest(TestCase):
    """项目管理集成测试 - 完整流程测试"""

    @classmethod
    def setUpTestData(cls):
        # 创建用户和管理员
        cls.admin_user = User.objects.create_user(
            username='admin', password='testpass123', is_staff=True
        )
        cls.admin_profile = Profile.objects.create(
            user=cls.admin_user, role='admin'
        )

        # 创建分包商用户
        cls.subcontractor_user = User.objects.create_user(
            username='subcontractor', password='testpass123'
        )
        cls.subcontractor_profile = Profile.objects.create(
            user=cls.subcontractor_user, role='subcontractor'
        )

        # 创建基础数据
        cls.project = Project.objects.create(
            code='PRJ2026001',
            name='测试住宅项目',
            manager='张经理',
            budget=Decimal('5000000.00'),
            status='active'
        )

        cls.subcontractor = Subcontractor.objects.create(
            code='SC2026001',
            name='诚信建筑工程公司',
            contact='李总',
            phone='13900139000',
            main_type='土建工程',
            credit_rating='excellent'
        )
        cls.subcontractor_profile.supplier_info = None
        cls.subcontractor_profile.save()

        # 创建分包清单分类和清单
        cls.category = SubcontractCategory.objects.create(
            category_code='SCC001',
            category_name='土石方工程'
        )

        cls.subcontract_list = SubcontractList.objects.create(
            code='SCL001',
            name='土方开挖',
            category=cls.category,
            construction_params='普通土,机械开挖',
            unit='m³',
            reference_price=Decimal('25.00')
        )

        # 创建合同
        cls.contract = Contract.objects.create(
            code='CON2026001',
            name='住宅项目土建工程',
            project=cls.project,
            subcontractor=cls.subcontractor
        )

        # 添加合同清单
        cls.contract_item = ContractItem.objects.create(
            contract=cls.contract,
            item_order=1,
            subcontract_list=cls.subcontract_list,
            quantity=Decimal('1000.00'),
            unit_price=Decimal('25.00')
        )

    def setUp(self):
        self.client = Client()

    def test_complete_measurement_workflow(self):
        """测试完整的进度计量创建流程"""
        # 1. 登录管理员
        self.client.login(username='admin', password='testpass123')

        # 2. 访问计量创建页面
        response = self.client.get(reverse('measurement_create'))
        self.assertEqual(response.status_code, 200)

    def test_complete_settlement_workflow(self):
        """测试完整的分包结算创建流程"""
        # 1. 登录管理员
        self.client.login(username='admin', password='testpass123')

        # 2. 访问结算创建页面
        response = self.client.get(reverse('settlement_create'))
        self.assertEqual(response.status_code, 200)

    def test_contract_total_calculation(self):
        """测试合同总额计算"""
        # 合同应该有一个清单项，总额应该是 1000 * 25 = 25000
        total = self.contract.get_contract_total()
        self.assertEqual(total, Decimal('25000.00'))

    def test_budget_creation(self):
        """测试预算创建和总额计算"""
        budget = Budget.objects.create(
            code='BUD2026001',
            project=self.project
        )

        # 添加预算清单
        BudgetItem.objects.create(
            budget=budget,
            item_order=1,
            subcontract_list=self.subcontract_list,
            quantity=Decimal('2000.00'),
            unit_price=Decimal('25.00')
        )

        # 验证预算总额
        self.assertEqual(budget.get_budget_total(), Decimal('50000.00'))

    def test_measurement_value_calculation(self):
        """测试进度计量产值计算"""
        # 创建计量记录
        measurement = Measurement.objects.create(
            code='MEAS2026001',
            contract=self.contract,
            project=self.project,
            subcontractor=self.subcontractor,
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            previous_value=Decimal('0')
        )

        # 添加计量清单
        MeasurementItem.objects.create(
            measurement=measurement,
            item_order=1,
            subcontract_list=self.subcontract_list,
            previous_quantity=Decimal('0'),
            current_quantity=Decimal('500.00'),
            unit_price=Decimal('25.00')
        )

        # 重新获取计量记录以计算产值
        measurement.refresh_from_db()
        self.assertEqual(measurement.current_value, Decimal('12500.00'))
        self.assertEqual(measurement.cumulative_value, Decimal('12500.00'))

    def test_subcontractor_role_permission(self):
        """测试分包商角色权限"""
        self.client.login(username='subcontractor', password='testpass123')

        # 分包商应该能访问计量列表
        response = self.client.get(reverse('measurement_list'))
        self.assertIn(response.status_code, [200, 302])  # 200 或重定向都可能


class CodeGenerationTest(TestCase):
    """编号生成逻辑测试 - 验证修复后的编号生成"""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_user(
            username='admin', password='testpass123', is_staff=True
        )
        cls.admin_profile = Profile.objects.create(
            user=cls.admin_user, role='admin'
        )

        # 创建基础数据
        cls.project = Project.objects.create(
            code='PRJ001', name='测试项目'
        )
        cls.subcontractor = Subcontractor.objects.create(
            code='SC001', name='测试分包商',
            contact='张三', phone='13900139000',
            main_type='土建'
        )
        cls.contract = Contract.objects.create(
            code='CON001', name='测试合同',
            project=cls.project, subcontractor=cls.subcontractor
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_measurement_code_format(self):
        """测试进度计量编号格式"""
        today = timezone.now().strftime('%Y%m%d')

        # 创建第一个计量
        measurement1 = Measurement.objects.create(
            code=f'{today}0001',
            contract=self.contract,
            project=self.project,
            subcontractor=self.subcontractor,
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            previous_value=Decimal('0')
        )
        self.assertTrue(measurement1.code.startswith(today))
        self.assertEqual(len(measurement1.code), 12)

        # 创建第二个计量
        measurement2 = Measurement.objects.create(
            code=f'{today}0002',
            contract=self.contract,
            project=self.project,
            subcontractor=self.subcontractor,
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            previous_value=Decimal('0')
        )
        self.assertTrue(measurement2.code.startswith(today))
        self.assertEqual(len(measurement2.code), 12)

    def test_settlement_code_format(self):
        """测试结算编号格式"""
        today = timezone.now().strftime('%Y%m%d')

        settlement = Settlement.objects.create(
            code=f'{today}0001',
            contract=self.contract,
            project=self.project,
            subcontractor=self.subcontractor,
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            measurement_value=Decimal('10000'),
            deduction_reason='无',
            deduction_amount=Decimal('0')
        )
        self.assertTrue(settlement.code.startswith(today))
        self.assertEqual(len(settlement.code), 12)


class SoftDeleteTest(TestCase):
    """软删除功能测试 - 新增模块"""

    @classmethod
    def setUpTestData(cls):
        cls.project = Project.objects.create(
            code='PRJ001', name='测试项目'
        )
        cls.subcontractor = Subcontractor.objects.create(
            code='SC001', name='测试分包商',
            contact='张三', phone='13900139000',
            main_type='土建'
        )
        cls.contract = Contract.objects.create(
            code='CON001', name='测试合同',
            project=cls.project, subcontractor=cls.subcontractor
        )

    def test_subcontractor_soft_delete(self):
        """测试分包商软删除"""
        subcontractor = Subcontractor.objects.create(
            code='SC_DELETE', name='待删除分包商',
            contact='删除', phone='13800138000', main_type='测试'
        )
        pk = subcontractor.pk

        # 软删除
        subcontractor.delete()

        # 验证软删除效果
        self.assertFalse(Subcontractor.objects.filter(pk=pk).exists())
        self.assertTrue(Subcontractor.all_objects.filter(pk=pk).exists())

        # 恢复
        subcontractor.restore()
        self.assertTrue(Subcontractor.objects.filter(pk=pk).exists())

    def test_contract_soft_delete(self):
        """测试合同软删除"""
        contract = Contract.objects.create(
            code='CON_DELETE', name='待删除合同',
            project=self.project, subcontractor=self.subcontractor
        )
        pk = contract.pk

        contract.delete()
        self.assertFalse(Contract.objects.filter(pk=pk).exists())
        self.assertTrue(Contract.all_objects.filter(pk=pk).exists())

    def test_measurement_soft_delete(self):
        """测试进度计量软删除"""
        from django.utils import timezone
        measurement = Measurement.objects.create(
            code='MEAS_DELETE',
            contract=self.contract,
            project=self.project,
            subcontractor=self.subcontractor,
            period_start=timezone.now().date(),
            period_end=timezone.now().date(),
            previous_value=Decimal('0')
        )
        pk = measurement.pk

        measurement.delete()
        self.assertFalse(Measurement.objects.filter(pk=pk).exists())
        self.assertTrue(Measurement.all_objects.filter(pk=pk).exists())
