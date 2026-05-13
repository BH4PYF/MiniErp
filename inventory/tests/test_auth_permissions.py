from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from ..models import Profile, Category, Material, Supplier, Project, PurchasePlan, Delivery
from decimal import Decimal


class ViewTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testuser', password='testpass123', first_name='测试'
        )
        cls.profile = Profile.objects.create(user=cls.user, role='admin', phone='12345678')

    def login(self):
        self.client.login(username='testuser', password='testpass123')


class DashboardViewTest(ViewTestBase):
    def test_dashboard_redirect_if_not_logged_in(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_dashboard_access_logged_in(self):
        self.login()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inventory/dashboard.html')


class LoginViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass123')
        Profile.objects.create(user=cls.user, role='management')

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')

    def test_login_success(self):
        user = User.objects.create_user(username='login_test_user', password='pass12345')
        Profile.objects.create(user=user, role='management')
        response = self.client.post(reverse('login'), {
            'username': 'login_test_user', 'password': 'pass12345'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

    def test_login_failure(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser', 'password': 'wrongpass'
        })
        self.assertEqual(response.status_code, 200)

    def test_login_rate_limit(self):
        for _ in range(6):
            self.client.post(reverse('login'), {
                'username': 'testuser', 'password': 'wrongpass'
            })
        response = self.client.post(reverse('login'), {
            'username': 'testuser', 'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 200)


class APIPermissionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        cls.admin = User.objects.create_user(username='admin', password='pass12345')
        Profile.objects.create(user=cls.admin, role='admin')
        
        # 添加Django权限
        material_content_type = ContentType.objects.get_for_model(Material)
        material_permissions = Permission.objects.filter(content_type=material_content_type)
        
        project_content_type = ContentType.objects.get_for_model(Project)
        project_permissions = Permission.objects.filter(content_type=project_content_type)
        
        supplier_content_type = ContentType.objects.get_for_model(Supplier)
        supplier_permissions = Permission.objects.filter(content_type=supplier_content_type)
        
        cls.admin.user_permissions.add(*material_permissions)
        cls.admin.user_permissions.add(*project_permissions)
        cls.admin.user_permissions.add(*supplier_permissions)

        cls.management_user = User.objects.create_user(username='management', password='pass12345')
        Profile.objects.create(user=cls.management_user, role='management')

        cls.supplier_user = User.objects.create_user(username='supplier', password='pass12345')
        Profile.objects.create(user=cls.supplier_user, role='supplier')

        cls.category = Category.objects.create(name="钢材", code="STEEL")
        cls.material = Material.objects.create(
            name="螺纹钢", code="HRB400", category=cls.category, unit="吨"
        )

    def test_material_api_unauthorized(self):
        response = self.client.get(reverse('material_detail_api', args=[self.material.id]))
        self.assertEqual(response.status_code, 302)

    def test_material_api_admin(self):
        self.client.login(username='admin', password='pass12345')
        response = self.client.get(reverse('material_detail_api', args=[self.material.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], "螺纹钢")

    def test_supplier_list_non_admin_rejected(self):
        self.client.login(username='supplier', password='pass12345')
        response = self.client.get(reverse('supplier_list'))
        self.assertEqual(response.status_code, 302)

    def test_user_list_non_admin_rejected(self):
        self.client.login(username='management', password='pass12345')
        response = self.client.get(reverse('user_list'))
        self.assertEqual(response.status_code, 302)

    def test_user_delete_self_rejected(self):
        self.client.login(username='admin', password='pass12345')
        response = self.client.post(reverse('user_delete', args=[self.admin.pk]))
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], '不能删除自己')


class PermissionMatrixTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="钢材", code="STEEL_P")
        cls.supplier_obj = Supplier.objects.create(
            name="权限测试供应商", code="SUP_P01", contact="李四",
            phone="13900139000", main_type=cls.category,
        )
        cls.material = Material.objects.create(
            name="权限测试材料", code="MT_P01", category=cls.category, unit="吨",
        )
        cls.project = Project.objects.create(name="权限测试项目", code="P_P01")

        cls.users = {}
        for role in ('admin', 'management', 'supplier'):
            user = User.objects.create_user(username=f'perm_{role}', password='pass12345')
            kwargs = {'user': user, 'role': role}
            if role == 'supplier':
                kwargs['supplier_info'] = cls.supplier_obj
            Profile.objects.create(**kwargs)
            cls.users[role] = user

    def _check_access(self, url, role, expected_allowed):
        self.client.login(username=f'perm_{role}', password='pass12345')
        response = self.client.get(url)
        if expected_allowed:
            self.assertIn(response.status_code, [200, 302])
            if response.status_code == 302:
                self.assertNotIn('/login/', response.url)
        else:
            if response.status_code in [302, 403]:
                return
            self.fail(f'{role} 不应访问 {url}，实际状态码 {response.status_code}')

    def test_admin_only_endpoints(self):
        admin_urls = [
            reverse('project_list'),
            reverse('material_list'),
            reverse('supplier_list'),
            reverse('user_list'),
            reverse('settings_page'),
        ]
        for url in admin_urls:
            self._check_access(url, 'admin', True)
            self._check_access(url, 'management', False)
            self._check_access(url, 'supplier', False)

    def test_delivery_access_by_role(self):
        url = reverse('delivery_list')
        for role in ('admin', 'supplier'):
            self._check_access(url, role, True)

    def test_inbound_access_by_role(self):
        url = reverse('inbound_list')
        self._check_access(url, 'admin', True)
        self._check_access(url, 'supplier', False)

    def test_report_access_by_role(self):
        url = reverse('report_page')
        for role in ('admin', 'management'):
            self._check_access(url, role, True)
        self._check_access(url, 'supplier', False)

    def test_api_get_only(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        admin_user = self.users['admin']
        
        # 添加Django权限
        material_content_type = ContentType.objects.get_for_model(Material)
        material_permissions = Permission.objects.filter(content_type=material_content_type)
        
        project_content_type = ContentType.objects.get_for_model(Project)
        project_permissions = Permission.objects.filter(content_type=project_content_type)
        
        supplier_content_type = ContentType.objects.get_for_model(Supplier)
        supplier_permissions = Permission.objects.filter(content_type=supplier_content_type)
        
        admin_user.user_permissions.add(*material_permissions)
        admin_user.user_permissions.add(*project_permissions)
        admin_user.user_permissions.add(*supplier_permissions)
        
        self.client.login(username='perm_admin', password='pass12345')
        post_only_apis = [
            reverse('material_detail_api', args=[self.material.pk]),
            reverse('supplier_detail_api', args=[self.supplier_obj.pk]),
            reverse('project_detail_api', args=[self.project.pk]),
        ]
        for url in post_only_apis:
            response = self.client.post(url)
            self.assertEqual(response.status_code, 405)
