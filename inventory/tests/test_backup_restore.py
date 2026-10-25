import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from ..models import (
    Budget, BudgetItem, Category, Contract, ContractItem, Delivery,
    InboundRecord, Material, MaterialPlan, MaterialPlanItem, Measurement,
    MeasurementItem, Profile, Project, PurchasePlan, Settlement,
    SettlementItem, SubcontractCategory, SubcontractList, Subcontractor,
    Supplier,
)
from ..services.backup_service import (
    RESTORE_LABELS, RestoreError, backup_json_default,
    build_backup_data, restore_backup_data,
)


def _dump(data):
    return json.loads(json.dumps(data, default=backup_json_default))


class BackupRestoreTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='backup_user', password='pass12345', first_name='备份'
        )
        cls.profile = Profile.objects.create(
            user=cls.user, role='admin', phone='13800000000'
        )
        cls.category = Category.objects.create(code='CAT01', name='钢材')
        cls.material = Material.objects.create(
            code='MAT01', name='钢筋', category=cls.category, unit='吨', spec='Φ25',
        )
        cls.project = Project.objects.create(code='PRJ01', name='测试项目')
        cls.supplier = Supplier.objects.create(
            code='SUP01', name='供应商A', contact='张三', phone='13800000001',
        )
        cls.subcontractor = Subcontractor.objects.create(
            code='SUB01', name='分包商A', contact='李四',
            phone='13900000000', main_type='土建',
        )
        cls.subcat = SubcontractCategory.objects.create(
            category_code='SCAT01', category_name='土建',
        )
        cls.sublist = SubcontractList.objects.create(
            code='SL01', name='混凝土', category=cls.subcat,
            construction_params='C30', unit='m3',
        )
        cls.budget = Budget.objects.create(code='B-0001', project=cls.project)
        BudgetItem.objects.create(
            budget=cls.budget, item_order=1, subcontract_list=cls.sublist,
            quantity=Decimal('10'), unit_price=Decimal('100'),
        )
        cls.contract = Contract.objects.create(
            code='C-0001', name='土建合同',
            project=cls.project, subcontractor=cls.subcontractor,
        )
        ContractItem.objects.create(
            contract=cls.contract, item_order=1, subcontract_list=cls.sublist,
            quantity=Decimal('20'), unit_price=Decimal('150'),
        )
        cls.measurement = Measurement.objects.create(
            code='M-0001', contract=cls.contract, project=cls.project,
            subcontractor=cls.subcontractor,
            period_start=date(2026, 1, 1), period_end=date(2026, 1, 31),
            previous_value=Decimal('0'),
        )
        MeasurementItem.objects.create(
            measurement=cls.measurement, item_order=1,
            subcontract_list=cls.sublist, previous_quantity=Decimal('0'),
            current_quantity=Decimal('10'), unit_price=Decimal('150'),
        )
        cls.settlement = Settlement.objects.create(
            code='S-0001', contract=cls.contract, project=cls.project,
            subcontractor=cls.subcontractor,
            period_start=date(2026, 1, 1), period_end=date(2026, 1, 31),
            deduction_reason='质保金', deduction_amount=Decimal('50'),
        )
        SettlementItem.objects.create(
            settlement=cls.settlement, item_order=1,
            subcontract_list=cls.sublist, measurement_quantity=Decimal('10'),
            adjusted_quantity=Decimal('10'), unit_price=Decimal('150'),
        )
        cls.material_plan = MaterialPlan.objects.create(
            project=cls.project, plan_number='MP-001', created_by=cls.user,
        )
        MaterialPlanItem.objects.create(
            material_plan=cls.material_plan, material=cls.material,
            quantity=Decimal('5'), unit='吨', unit_price=Decimal('100'),
        )
        cls.inbound = InboundRecord.objects.create(
            no='IN-001', project=cls.project, material=cls.material,
            date=date(2026, 1, 5), quantity=Decimal('5'),
            unit_price=Decimal('100'), supplier=cls.supplier,
            spec='Φ25', operator=cls.user,
        )
        cls.purchase_plan = PurchasePlan.objects.create(
            no='PP-001', project=cls.project, material=cls.material,
            quantity=Decimal('3'), unit_price=Decimal('50'), operator=cls.user,
        )
        cls.delivery = Delivery.objects.create(
            no='DL-001', purchase_plan=cls.purchase_plan,
            actual_quantity=Decimal('3'), actual_unit_price=Decimal('50'),
            shipping_method='special', supplier=cls.supplier,
        )


class BackupDataTest(BackupRestoreTestBase):
    def test_backup_has_all_sections_and_is_json_serializable(self):
        data = build_backup_data()
        self.assertIn('timestamp', data)
        for section in RESTORE_LABELS:
            self.assertIn(section, data)

        raw = json.dumps(data, default=backup_json_default, ensure_ascii=False)
        restored = json.loads(raw)
        self.assertEqual(len(restored['profiles']), 1)
        self.assertEqual(restored['profiles'][0]['supplier_info_id'], None)
        self.assertEqual(restored['users'][0]['username'], 'backup_user')

    def test_backup_includes_soft_deleted_records(self):
        extra = Supplier.objects.create(code='SUP_DEL', name='已删除供应商')
        extra.delete()

        data = build_backup_data()
        row = next(r for r in data['suppliers'] if r['code'] == 'SUP_DEL')
        self.assertTrue(row['is_deleted'])
        self.assertIsNotNone(row['deleted_at'])


class RestoreDataTest(BackupRestoreTestBase):
    def test_round_trip_restores_records_and_recalculates_totals(self):
        data = _dump(build_backup_data())

        Project.objects.filter(pk=self.project.pk).update(name='被改名')
        BudgetItem.objects.all().delete()
        ContractItem.objects.all().delete()
        MeasurementItem.objects.all().delete()
        SettlementItem.objects.all().delete()
        MaterialPlanItem.objects.all().delete()
        InboundRecord.all_objects.filter(pk=self.inbound.pk).hard_delete()
        Delivery.all_objects.filter(pk=self.delivery.pk).hard_delete()
        PurchasePlan.all_objects.filter(pk=self.purchase_plan.pk).hard_delete()

        counts = restore_backup_data(data)

        self.project.refresh_from_db()
        self.assertEqual(self.project.name, '测试项目')
        self.assertEqual(counts['budget_items'], 1)
        self.assertEqual(counts['contract_items'], 1)
        self.assertEqual(counts['measurement_items'], 1)
        self.assertEqual(counts['settlement_items'], 1)
        self.assertEqual(counts['material_plan_items'], 1)
        self.assertEqual(counts['inbound_records'], 1)
        self.assertEqual(counts['deliveries'], 1)
        self.assertEqual(counts['purchase_plans'], 1)

        self.assertEqual(self.budget.get_budget_total(), Decimal('1000.00'))
        self.assertEqual(self.contract.get_contract_total(), Decimal('3000.00'))

        measurement = Measurement.objects.get(code='M-0001')
        self.assertEqual(measurement.current_value, Decimal('1500.00'))
        self.assertEqual(measurement.cumulative_value, Decimal('1500.00'))

        settlement = Settlement.objects.get(code='S-0001')
        self.assertEqual(settlement.final_amount, Decimal('1450.00'))

        plan = MaterialPlan.objects.get(plan_number='MP-001')
        self.assertEqual(plan.total_amount, Decimal('500.00'))

        inbound = InboundRecord.objects.get(no='IN-001')
        self.assertEqual(inbound.material_id, self.material.pk)
        self.assertEqual(inbound.operator_id, self.user.pk)
        self.assertEqual(inbound.spec, 'Φ25')

        delivery = Delivery.objects.get(no='DL-001')
        self.assertEqual(delivery.purchase_plan.no, 'PP-001')

    def test_soft_deleted_state_is_preserved(self):
        extra = Supplier.objects.create(code='SUP_DEL', name='已删除供应商')
        extra.delete()
        data = _dump(build_backup_data())

        Supplier.all_objects.filter(code='SUP_DEL').hard_delete()
        restore_backup_data(data)

        restored = Supplier.all_objects.get(code='SUP_DEL')
        self.assertTrue(restored.is_deleted)
        self.assertFalse(Supplier.objects.filter(code='SUP_DEL').exists())

    def test_missing_reference_raises_and_rolls_back(self):
        data = _dump(build_backup_data())
        data['projects'][0]['name'] = '回滚名称'
        data['measurements'].append({
            'code': 'M-BAD',
            'contract_id': 999999,
            'project_id': self.project.pk,
            'subcontractor_id': self.subcontractor.pk,
            'period_start': '2026-02-01',
            'period_end': '2026-02-28',
            'previous_value': '0',
            'current_value': '0',
            'cumulative_value': '0',
        })

        with self.assertRaises(RestoreError):
            restore_backup_data(data)

        self.project.refresh_from_db()
        self.assertEqual(self.project.name, '测试项目')
        self.assertFalse(Measurement.objects.filter(code='M-BAD').exists())


class RestoreEndpointTest(BackupRestoreTestBase):
    def test_admin_can_restore_uploaded_backup(self):
        self.client.force_login(self.user)
        payload = json.dumps(
            build_backup_data(), default=backup_json_default, ensure_ascii=False
        ).encode('utf-8')
        upload = SimpleUploadedFile(
            'backup.json', payload, content_type='application/json'
        )

        response = self.client.post(reverse('restore_data'), {'file': upload})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['success'])
        self.assertIn('项目', body['message'])
        self.assertEqual(body['restored']['projects'], 1)

    def test_restore_rejects_incomplete_reference(self):
        self.client.force_login(self.user)
        payload = json.dumps({
            'timestamp': '2026-01-01T00:00:00',
            'measurements': [{
                'code': 'M-ORPHAN',
                'contract_id': 424242,
                'period_start': '2026-01-01',
                'period_end': '2026-01-31',
            }],
        }).encode('utf-8')
        upload = SimpleUploadedFile(
            'broken.json', payload, content_type='application/json'
        )

        response = self.client.post(reverse('restore_data'), {'file': upload})

        self.assertEqual(response.status_code, 400)
        self.assertIn('已回滚', response.json()['error'])
