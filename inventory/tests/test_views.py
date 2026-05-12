import pytest
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from ..models import Category, Material, Project, Supplier, InboundRecord, Profile


class MaterialViewsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        cls.user = User.objects.create_user(username='admin', password='testpass123', is_staff=True)
        cls.profile = Profile.objects.create(user=cls.user, role='admin')
        
        # 添加Django权限
        material_content_type = ContentType.objects.get_for_model(Material)
        material_permissions = Permission.objects.filter(content_type=material_content_type)
        cls.user.user_permissions.add(*material_permissions)
        
        cls.category = Category.objects.create(code='TEST', name='测试分类')
        cls.material = Material.objects.create(
            code='MAT001', name='测试材料', category=cls.category,
            unit='个', standard_price=Decimal('10.00'), safety_stock=10
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_material_list_view(self):
        response = self.client.get(reverse('material_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '测试材料')
        self.assertContains(response, 'MAT001')

    def test_material_save_create(self):
        data = {
            'name': '新材料',
            'category_id': self.category.id,
            'unit': '个',
            'standard_price': '20.00',
            'safety_stock': '5',
            'spec': '规格1',
            'remark': '测试备注'
        }
        response = self.client.post(reverse('material_save'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Material.objects.filter(name='新材料').exists())


class ProjectViewsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        cls.user = User.objects.create_user(username='admin', password='testpass123', is_staff=True)
        cls.profile = Profile.objects.create(user=cls.user, role='admin')
        
        # 添加项目权限
        project_content_type = ContentType.objects.get_for_model(Project)
        project_permissions = Permission.objects.filter(content_type=project_content_type)
        cls.user.user_permissions.add(*project_permissions)
        
        cls.project = Project.objects.create(
            code='PRJ001', name='测试项目', manager='张三',
            budget=Decimal('100000'), status='active'
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_project_list_view(self):
        response = self.client.get(reverse('project_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '测试项目')
        self.assertContains(response, 'PRJ001')

    def test_project_save_create(self):
        data = {
            'code': 'PRJ002',
            'name': '新项目',
            'manager': '李四',
            'budget': '50000',
            'status': 'active'
        }
        response = self.client.post(reverse('project_save'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result.get('success'))

    def test_project_detail_api(self):
        response = self.client.get(reverse('project_detail_api', kwargs={'pk': self.project.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 'PRJ001')
        self.assertEqual(data['name'], '测试项目')


class SupplierViewsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        cls.user = User.objects.create_user(username='admin', password='testpass123', is_staff=True)
        cls.profile = Profile.objects.create(user=cls.user, role='admin')
        
        # 添加供应商权限
        supplier_content_type = ContentType.objects.get_for_model(Supplier)
        supplier_permissions = Permission.objects.filter(content_type=supplier_content_type)
        cls.user.user_permissions.add(*supplier_permissions)
        
        cls.category = Category.objects.create(code='TEST', name='测试分类')
        cls.supplier = Supplier.objects.create(
            code='SUP001', name='测试供应商', contact='王五',
            phone='13800138000', credit_rating='good'
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_supplier_list_view(self):
        response = self.client.get(reverse('supplier_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '测试供应商')

    def test_supplier_save_create(self):
        data = {
            'code': 'SUP002',
            'name': '新供应商',
            'contact': '赵六',
            'phone': '13900139000',
            'address': '新地址',
            'main_type': self.category.id,
            'credit_rating': 'good',
            'remark': '测试供应商'
        }
        response = self.client.post(reverse('supplier_save'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Supplier.objects.filter(name='新供应商').exists())


class InboundViewsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='admin', password='testpass123', is_staff=True)
        cls.profile = Profile.objects.create(user=cls.user, role='admin')
        cls.category = Category.objects.create(code='TEST', name='测试分类')
        cls.material = Material.objects.create(
            code='MAT001', name='测试材料', category=cls.category,
            unit='个', spec='标准规格', standard_price=Decimal('10.00')
        )
        cls.project = Project.objects.create(code='PRJ001', name='测试项目')
        cls.supplier = Supplier.objects.create(code='SUP001', name='测试供应商')

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_inbound_list_view(self):
        response = self.client.get(reverse('inbound_list'))
        self.assertEqual(response.status_code, 200)

    def test_inbound_save(self):
        data = {
            'project_id': self.project.id,
            'material_id': self.material.id,
            'supplier_id': self.supplier.id,
            'date': '2026-03-27',
            'quantity': '10',
            'unit_price': '15.00',
            'batch_no': 'BATCH001',
            'spec': '测试规格',
            'remark': '测试入库'
        }
        response = self.client.post(reverse('inbound_save'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'success': True, 'message': '保存成功'})
        self.assertTrue(InboundRecord.objects.exists())

    def test_inbound_detail_api(self):
        inbound = InboundRecord.objects.create(
            no='IN20260327001', project=self.project, material=self.material,
            supplier=self.supplier, date='2026-03-27', quantity=Decimal('5'),
            unit_price=Decimal('12.00'), total_amount=Decimal('60.00'),
            operator=self.user, spec='测试规格'
        )
        response = self.client.get(reverse('inbound_detail_api', kwargs={'pk': inbound.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['no'], 'IN20260327001')
        self.assertEqual(data['quantity'], '5.00')


class DashboardViewsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='admin', password='testpass123', is_staff=True)
        cls.profile = Profile.objects.create(user=cls.user, role='admin')

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_dashboard_view(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '材料管理系统')


class ReportViewsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='admin', password='testpass123', is_staff=True)
        cls.profile = Profile.objects.create(user=cls.user, role='admin')
        cls.category = Category.objects.create(code='TEST', name='测试分类')
        cls.material = Material.objects.create(
            code='MAT001', name='测试材料', category=cls.category,
            unit='个', spec='标准规格', standard_price=Decimal('10.00')
        )
        cls.project = Project.objects.create(code='PRJ001', name='测试项目')
        cls.supplier = Supplier.objects.create(code='SUP001', name='测试供应商')
        cls.inbound = InboundRecord.objects.create(
            no='IN20260327001', project=cls.project, material=cls.material,
            supplier=cls.supplier, date='2026-03-27', quantity=Decimal('10'),
            unit_price=Decimal('15.00'), total_amount=Decimal('150.00'),
            operator=cls.user, spec='测试规格'
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_report_page_view(self):
        response = self.client.get(reverse('report_page'))
        self.assertEqual(response.status_code, 200)

    def test_chart_data_api(self):
        response = self.client.get(reverse('chart_data_api'), {'type': 'stock'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('data', data)


class PurchasePlanViewsTest(TestCase):
    """采购计划视图测试"""
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='admin', password='testpass123', is_staff=True)
        cls.profile = Profile.objects.create(user=cls.user, role='admin')
        cls.category = Category.objects.create(code='TEST', name='测试分类')
        cls.material = Material.objects.create(
            code='MAT001', name='测试材料', category=cls.category,
            unit='个', spec='标准规格', standard_price=Decimal('10.00')
        )
        cls.project = Project.objects.create(code='PRJ001', name='测试项目')
        cls.supplier = Supplier.objects.create(code='SUP001', name='测试供应商')
        from ..models import PurchasePlan
        cls.plan_pending = PurchasePlan.objects.create(
            no='PP20260327001', project=cls.project, material=cls.material,
            quantity=Decimal('10'), unit_price=Decimal('10.00'), total_amount=Decimal('100.00'),
            status=PurchasePlan.STATUS_PENDING, operator=cls.user,
            planned_date='2026-04-01', spec='测试规格'
        )
        cls.plan_purchasing = PurchasePlan.objects.create(
            no='PP20260327002', project=cls.project, material=cls.material,
            quantity=Decimal('20'), unit_price=Decimal('10.00'), total_amount=Decimal('200.00'),
            status=PurchasePlan.STATUS_PURCHASING, operator=cls.user,
            planned_date='2026-04-01', spec='测试规格'
        )
        cls.plan_shipped = PurchasePlan.objects.create(
            no='PP20260327003', project=cls.project, material=cls.material,
            quantity=Decimal('30'), unit_price=Decimal('10.00'), total_amount=Decimal('300.00'),
            status=PurchasePlan.STATUS_SHIPPED, operator=cls.user,
            planned_date='2026-04-01', spec='测试规格'
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_purchase_plan_list_view(self):
        """测试采购计划列表页面"""
        from ..models import PurchasePlan
        response = self.client.get(reverse('purchase_plan_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PP20260327001')

    def test_purchase_plan_save_create(self):
        """测试创建采购计划"""
        from ..models import PurchasePlan
        data = {
            'project_id': self.project.id,
            'material_id': self.material.id,
            'supplier_id': self.supplier.id,
            'quantity': '15',
            'spec': '新规格',
            'planned_date': '2026-04-15',
            'remark': '测试创建'
        }
        response = self.client.post(reverse('purchase_plan_save'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result.get('success'))
        self.assertTrue(PurchasePlan.objects.filter(spec='标准规格').exists())

    def test_purchase_plan_save_update_pending(self):
        """测试编辑审批中的采购计划"""
        from ..models import PurchasePlan
        data = {
            'id': self.plan_pending.id,
            'project_id': self.project.id,
            'material_id': self.material.id,
            'supplier_id': self.supplier.id,
            'quantity': '25',
            'spec': '修改后的规格',
            'planned_date': '2026-04-20',
            'remark': '测试修改'
        }
        response = self.client.post(reverse('purchase_plan_save'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result.get('success'))
        self.plan_pending.refresh_from_db()
        self.assertEqual(self.plan_pending.quantity, Decimal('25'))
        self.assertEqual(self.plan_pending.spec, '标准规格')

    def test_purchase_plan_save_update_purchasing(self):
        """测试编辑采购中的采购计划"""
        from ..models import PurchasePlan
        data = {
            'id': self.plan_purchasing.id,
            'project_id': self.project.id,
            'material_id': self.material.id,
            'supplier_id': self.supplier.id,
            'quantity': '35',
            'spec': '修改后的规格2',
            'planned_date': '2026-04-25',
            'remark': '测试修改2'
        }
        response = self.client.post(reverse('purchase_plan_save'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result.get('success'))
        self.plan_purchasing.refresh_from_db()
        self.assertEqual(self.plan_purchasing.quantity, Decimal('35'))

    def test_purchase_plan_save_update_shipped_not_allowed(self):
        """测试已发货的采购计划不能编辑"""
        from ..models import PurchasePlan
        data = {
            'id': self.plan_shipped.id,
            'project_id': self.project.id,
            'material_id': self.material.id,
            'supplier_id': self.supplier.id,
            'quantity': '40',
            'spec': '不应该修改',
            'planned_date': '2026-04-30',
            'remark': '测试修改3'
        }
        response = self.client.post(reverse('purchase_plan_save'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        result = response.json()
        self.assertFalse(result.get('success'))
        self.assertIn('已发货', result.get('message', ''))

    def test_purchase_plan_delete_pending(self):
        """测试删除审批中的采购计划"""
        from ..models import PurchasePlan
        plan_id = self.plan_pending.pk
        response = self.client.post(
            reverse('purchase_plan_delete', kwargs={'pk': plan_id}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result.get('success'))
        # 验证对象已被硬删除
        self.assertFalse(PurchasePlan.objects.filter(pk=plan_id).exists())
        self.assertFalse(PurchasePlan.all_objects.filter(pk=plan_id).exists())

    def test_purchase_plan_delete_shipped_not_allowed(self):
        """测试已发货的采购计划不能删除"""
        from ..models import PurchasePlan
        response = self.client.post(
            reverse('purchase_plan_delete', kwargs={'pk': self.plan_shipped.pk}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        result = response.json()
        self.assertFalse(result.get('success'))


class SettingsViewsTest(TestCase):
    """系统设置视图测试"""
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='admin', password='testpass123', is_staff=True)
        cls.profile = Profile.objects.create(user=cls.user, role='admin')

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_settings_page_view(self):
        """测试设置页面"""
        response = self.client.get(reverse('settings_page'))
        self.assertEqual(response.status_code, 200)

    def test_init_categories(self):
        """测试初始化材料分类"""
        # 先删除现有分类
        Category.objects.all().delete()
        
        response = self.client.post(
            reverse('init_categories'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result.get('success'))
        # 验证是否创建了7个分类
        self.assertEqual(Category.objects.count(), 7)
        self.assertTrue(Category.objects.filter(name='钢筋').exists())
        self.assertTrue(Category.objects.filter(name='水泥').exists())

    def test_init_categories_skip_existing(self):
        """测试初始化时跳过已存在的分类"""
        # 先创建一个已存在的分类
        Category.objects.create(code='CAT0001', name='钢筋')
        initial_count = Category.objects.count()
        
        response = self.client.post(
            reverse('init_categories'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result.get('success'))
        # 验证已存在的分类被跳过
        self.assertIn('跳过', result.get('message', ''))

    def test_clear_all_data(self):
        """测试清空所有数据"""
        # 先创建一些测试数据
        Category.objects.create(code='TEST001', name='测试分类')
        Project.objects.create(code='PRJ001', name='测试项目')
        
        response = self.client.post(
            reverse('clear_all_data'),
            {'confirm': 'CONFIRM'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result.get('success'))
        # 验证数据被清空
        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(Project.objects.count(), 0)
        # 验证用户仍然存在
        self.assertTrue(User.objects.filter(username='admin').exists())


class MeasurementViewsTest(TestCase):
    """进度计量视图测试"""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from ..models import Subcontractor, Contract, Project

        cls.user = User.objects.create_user(username='admin', password='testpass123', is_staff=True)
        cls.profile = Profile.objects.create(user=cls.user, role='admin')

        cls.project = Project.objects.create(
            code='PRJ001', name='测试项目', manager='张三',
            budget=Decimal('100000'), status='active'
        )
        cls.subcontractor = Subcontractor.objects.create(
            code='SC001', name='测试分包商', contact='李四',
            phone='13800138000', main_type='土建工程', credit_rating='good'
        )
        cls.contract = Contract.objects.create(
            code='CON001', name='测试合同', project=cls.project,
            subcontractor=cls.subcontractor
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_measurement_list_view(self):
        """测试进度计量列表页面"""
        response = self.client.get(reverse('measurement_list'))
        self.assertEqual(response.status_code, 200)

    def test_measurement_create_view(self):
        """测试进度计量创建页面"""
        response = self.client.get(reverse('measurement_create'))
        self.assertEqual(response.status_code, 200)


class SettlementViewsTest(TestCase):
    """分包结算视图测试"""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from ..models import Subcontractor, Contract, Project

        cls.user = User.objects.create_user(username='admin', password='testpass123', is_staff=True)
        cls.profile = Profile.objects.create(user=cls.user, role='admin')

        cls.project = Project.objects.create(
            code='PRJ001', name='测试项目', manager='张三',
            budget=Decimal('100000'), status='active'
        )
        cls.subcontractor = Subcontractor.objects.create(
            code='SC001', name='测试分包商', contact='李四',
            phone='13800138000', main_type='土建工程', credit_rating='good'
        )
        cls.contract = Contract.objects.create(
            code='CON001', name='测试合同', project=cls.project,
            subcontractor=cls.subcontractor
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_settlement_list_view(self):
        """测试分包结算列表页面"""
        response = self.client.get(reverse('settlement_list'))
        self.assertEqual(response.status_code, 200)

    def test_settlement_create_view(self):
        """测试分包结算创建页面"""
        response = self.client.get(reverse('settlement_create'))
        self.assertEqual(response.status_code, 200)


class SubcontractorViewsTest(TestCase):
    """分包商视图测试"""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from ..models import Subcontractor

        cls.user = User.objects.create_user(username='admin', password='testpass123', is_staff=True)
        cls.profile = Profile.objects.create(user=cls.user, role='admin')

        cls.subcontractor = Subcontractor.objects.create(
            code='SC001', name='测试分包商', contact='王五',
            phone='13900139000', main_type='装饰工程', credit_rating='good'
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_subcontractor_list_view(self):
        """测试分包商列表页面"""
        response = self.client.get(reverse('subcontractor_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '测试分包商')
        self.assertContains(response, 'SC001')


class ContractViewsTest(TestCase):
    """合同视图测试"""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from ..models import Subcontractor, Project, Contract

        cls.user = User.objects.create_user(username='admin', password='testpass123', is_staff=True)
        cls.profile = Profile.objects.create(user=cls.user, role='admin')

        cls.project = Project.objects.create(
            code='PRJ001', name='测试项目', manager='张三'
        )
        cls.subcontractor = Subcontractor.objects.create(
            code='SC001', name='测试分包商', contact='李四',
            phone='13800138000', main_type='土建'
        )
        cls.contract = Contract.objects.create(
            code='CON001', name='测试合同', project=cls.project,
            subcontractor=cls.subcontractor
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin', password='testpass123')

    def test_contract_list_view(self):
        """测试合同列表页面"""
        response = self.client.get(reverse('contract_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '测试合同')
        self.assertContains(response, 'CON001')

