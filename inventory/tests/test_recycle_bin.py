from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import Category, Material, OperationLog, Profile


class RecycleBinTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_user(
            username='recycle_admin', password='pass12345'
        )
        Profile.objects.create(user=cls.admin_user, role='admin')
        cls.normal_user = User.objects.create_user(
            username='recycle_user', password='pass12345'
        )
        Profile.objects.create(user=cls.normal_user, role='management')

        cls.category = Category.objects.create(code='CAT01', name='钢材')
        cls.material = Material.objects.create(
            code='MAT01', name='钢筋', category=cls.category,
            unit='吨', spec='Φ25',
        )

    def login_admin(self):
        self.client.force_login(self.admin_user)


class RecycleBinPageTest(RecycleBinTestBase):
    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('recycle_bin'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_non_admin_redirected_to_dashboard(self):
        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('recycle_bin'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

    def test_page_lists_deleted_records(self):
        self.material.delete()
        self.login_admin()

        response = self.client.get(reverse('recycle_bin'), {'model': 'material'})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inventory/recycle_bin.html')
        self.assertEqual(response.context['total_deleted'], 1)
        self.assertContains(response, '钢筋')
        self.assertContains(response, 'MAT01')

    def test_search_filters_deleted_records(self):
        other = Material.objects.create(
            code='MAT02', name='水泥', category=self.category, unit='吨',
        )
        self.material.delete()
        other.delete()
        self.login_admin()

        response = self.client.get(
            reverse('recycle_bin'), {'model': 'material', 'q': 'MAT02'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '水泥')
        self.assertNotContains(response, '钢筋')


class RecycleBinRestoreTest(RecycleBinTestBase):
    def restore(self, model_key, pk, ajax=True):
        headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
        return self.client.post(
            reverse('recycle_bin_restore', args=[model_key, pk]), **headers
        )

    def test_restore_blocked_until_category_restored(self):
        self.category.delete()
        self.material.delete()
        self.login_admin()

        response = self.restore('material', self.material.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn('材料分类', response.json()['error'])
        self.assertTrue(
            Material.all_objects.get(pk=self.material.pk).is_deleted
        )

        self.restore('category', self.category.pk)
        response = self.restore('material', self.material.pk)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        self.material.refresh_from_db()
        self.assertFalse(self.material.is_deleted)
        self.assertIsNone(self.material.deleted_at)
        self.assertTrue(
            OperationLog.objects.filter(
                module='回收站', related_no='MAT01'
            ).exists()
        )

    def test_restore_requires_post(self):
        self.material.delete()
        self.login_admin()

        response = self.client.get(
            reverse('recycle_bin_restore', args=['material', self.material.pk])
        )

        self.assertEqual(response.status_code, 405)

    def test_restore_non_deleted_record_returns_404(self):
        self.login_admin()
        response = self.restore('material', self.material.pk)
        self.assertEqual(response.status_code, 404)

    def test_restore_unknown_model_returns_404(self):
        self.material.delete()
        self.login_admin()
        response = self.restore('unknown', self.material.pk)
        self.assertEqual(response.status_code, 404)

    def test_non_admin_cannot_restore(self):
        self.material.delete()
        self.client.force_login(self.normal_user)

        response = self.restore('material', self.material.pk)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            Material.all_objects.get(pk=self.material.pk).is_deleted
        )
