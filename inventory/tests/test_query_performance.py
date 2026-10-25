from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ..models import (
    Contract, ContractItem, Measurement, Profile, Project,
    SubcontractCategory, SubcontractList, Subcontractor,
)


class QueryCountMixin:
    def count_queries(self, url):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries)


class SubcontractorDashboardQueryTest(QueryCountMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='sub_user', password='pass12345'
        )
        cls.profile = Profile.objects.create(user=cls.user, role='subcontractor')
        cls.subcontractor = Subcontractor.objects.create(
            code='SUB01', name='分包商', contact='李四',
            phone='13900000000', main_type='土建',
        )
        cls.subcontractor.user_profiles.add(cls.profile)
        cls.project = Project.objects.create(code='PRJ01', name='项目')
        cls.subcat = SubcontractCategory.objects.create(
            category_code='SCAT01', category_name='土建',
        )
        cls.sublist = SubcontractList.objects.create(
            code='SL01', name='混凝土', category=cls.subcat,
            construction_params='C30', unit='m3',
        )
        cls.created = 0

    def create_contract(self):
        self.created += 1
        contract = Contract.objects.create(
            code=f'C{self.created:04d}', name=f'合同{self.created}',
            project=self.project, subcontractor=self.subcontractor,
        )
        ContractItem.objects.create(
            contract=contract, item_order=1, subcontract_list=self.sublist,
            quantity=Decimal('10'), unit_price=Decimal('100'),
        )
        Measurement.objects.create(
            code=f'M{self.created:04d}', contract=contract,
            project=self.project, subcontractor=self.subcontractor,
            period_start=date(2026, 1, 1), period_end=date(2026, 1, 31),
            current_value=Decimal('100'),
        )
        return contract

    def test_query_count_does_not_grow_with_contracts(self):
        self.client.force_login(self.user)
        self.create_contract()
        self.count_queries(reverse('dashboard'))  # 预热模板上下文缓存
        baseline = self.count_queries(reverse('dashboard'))

        for _ in range(5):
            self.create_contract()

        self.assertEqual(self.count_queries(reverse('dashboard')), baseline)


class ProjectSubcontractReportQueryTest(QueryCountMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='report_admin', password='pass12345'
        )
        Profile.objects.create(user=cls.user, role='admin')
        cls.project = Project.objects.create(code='PRJ01', name='项目')
        cls.subcontractor = Subcontractor.objects.create(
            code='SUB01', name='分包商', contact='李四',
            phone='13900000000', main_type='土建',
        )
        cls.subcat = SubcontractCategory.objects.create(
            category_code='SCAT01', category_name='土建',
        )
        cls.sublist = SubcontractList.objects.create(
            code='SL01', name='混凝土', category=cls.subcat,
            construction_params='C30', unit='m3',
        )
        cls.created = 0

    def create_contract(self):
        self.created += 1
        contract = Contract.objects.create(
            code=f'C{self.created:04d}', name=f'合同{self.created}',
            project=self.project, subcontractor=self.subcontractor,
        )
        ContractItem.objects.create(
            contract=contract, item_order=1, subcontract_list=self.sublist,
            quantity=Decimal('10'), unit_price=Decimal('100'),
        )
        return contract

    def report_url(self):
        return f"{reverse('report_project_subcontract')}?project_id={self.project.pk}"

    def test_query_count_does_not_grow_with_contracts(self):
        self.client.force_login(self.user)
        self.create_contract()
        cache.clear()
        self.count_queries(self.report_url())  # 预热缓存
        cache.clear()
        baseline = self.count_queries(self.report_url())

        for _ in range(5):
            self.create_contract()

        cache.clear()
        self.assertEqual(self.count_queries(self.report_url()), baseline)
