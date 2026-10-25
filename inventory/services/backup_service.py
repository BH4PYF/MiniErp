"""JSON 备份构建与恢复。

备份用于业务数据迁移/误删找回；完整的灾难恢复仍应使用数据库物理备份。
恢复按业务编号（code/no/plan_number/username）匹配记录，已存在的记录会被覆盖。
"""
import logging
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from inventory.models import (
    Budget, BudgetItem, Category, Contract, ContractItem, Delivery,
    InboundRecord, Material, MaterialPlan, MaterialPlanItem, Measurement,
    MeasurementItem, Profile, Project, PurchasePlan, Settlement,
    SettlementItem, SubcontractCategory, SubcontractList, Subcontractor,
    Supplier,
)

logger = logging.getLogger('inventory')

MAX_BACKUP_ROWS = 50000

RESTORE_LABELS = {
    'users': '用户',
    'profiles': '用户角色',
    'categories': '材料分类',
    'projects': '项目',
    'suppliers': '供应商',
    'subcontractors': '分包商',
    'subcontract_categories': '分包清单分类',
    'materials': '材料',
    'subcontract_lists': '分包清单',
    'budgets': '分包预算',
    'contracts': '分包合同',
    'measurements': '进度计量',
    'settlements': '分包结算',
    'material_plans': '材料计划',
    'inbound_records': '入库记录',
    'purchase_plans': '采购计划',
    'deliveries': '发货单',
    'budget_items': '预算明细',
    'contract_items': '合同明细',
    'measurement_items': '计量明细',
    'settlement_items': '结算明细',
    'material_plan_items': '材料计划明细',
}

AUTO_FIELDS = {'created_at', 'operate_time', 'create_time', 'update_time', 'updated_at'}


class RestoreError(Exception):
    """备份文件内容不完整或引用的数据不存在。"""


def backup_json_default(obj):
    """JSON 序列化 Decimal/日期，Decimal 用字符串保留精度。"""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f'无法序列化类型: {type(obj).__name__}')


def build_backup_data(max_rows=MAX_BACKUP_ROWS):
    """构建全量业务数据快照，包含软删除记录。"""
    return {
        'timestamp': timezone.now().isoformat(),
        'projects': list(Project.all_objects.values()[:max_rows]),
        'categories': list(Category.all_objects.values()[:max_rows]),
        'materials': list(Material.all_objects.values()[:max_rows]),
        'suppliers': list(Supplier.all_objects.values()[:max_rows]),
        'inbound_records': list(InboundRecord.all_objects.values()[:max_rows]),
        'purchase_plans': list(PurchasePlan.all_objects.values()[:max_rows]),
        'deliveries': list(Delivery.all_objects.values()[:max_rows]),
        'subcontractors': list(Subcontractor.all_objects.values()[:max_rows]),
        'subcontract_categories': list(SubcontractCategory.all_objects.values()[:max_rows]),
        'subcontract_lists': list(SubcontractList.all_objects.values()[:max_rows]),
        'budgets': list(Budget.all_objects.values()[:max_rows]),
        'budget_items': list(BudgetItem.objects.values()[:max_rows]),
        'contracts': list(Contract.all_objects.values()[:max_rows]),
        'contract_items': list(ContractItem.objects.values()[:max_rows]),
        'measurements': list(Measurement.all_objects.values()[:max_rows]),
        'measurement_items': list(MeasurementItem.objects.values()[:max_rows]),
        'settlements': list(Settlement.all_objects.values()[:max_rows]),
        'settlement_items': list(SettlementItem.objects.values()[:max_rows]),
        'material_plans': list(MaterialPlan.all_objects.values()[:max_rows]),
        'material_plan_items': list(MaterialPlanItem.objects.values()[:max_rows]),
        'profiles': list(
            Profile.objects.values(
                'user_id', 'role', 'phone', 'supplier_info_id',
            )[:max_rows]
        ),
        'users': list(
            User.objects.values(
                'id', 'username', 'first_name', 'last_name', 'email',
                'is_active', 'is_superuser',
            )[:max_rows]
        ),
    }


def _rows(data, section):
    rows = data.get(section)
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _index(rows):
    return {row['id']: row for row in rows if row.get('id') is not None}


def _manager(model):
    return getattr(model, 'all_objects', model.objects)


def _coerce(model, field_name, value):
    field = model._meta.get_field(field_name)
    if value == '' and field.null:
        value = None
    try:
        return field.to_python(value)
    except (ValidationError, ValueError, TypeError) as exc:
        raise RestoreError(
            f'{model._meta.verbose_name}字段“{field.verbose_name}”的值无效：{value!r}'
        ) from exc


def _upsert(model, lookup_field, row, scalar_fields, fk_resolvers):
    lookup_value = row.get(lookup_field)
    if not lookup_value:
        return None

    defaults = {}
    for field_name in scalar_fields:
        if field_name in row:
            defaults[field_name] = _coerce(model, field_name, row[field_name])
    for field_name, resolver in fk_resolvers.items():
        defaults[field_name] = resolver(row.get(f'{field_name}_id'))

    manager = _manager(model)
    obj, _ = manager.update_or_create(
        **{lookup_field: lookup_value}, defaults=defaults
    )
    force_fields = {f: defaults[f] for f in AUTO_FIELDS if f in defaults}
    if force_fields:
        # auto_now_add 字段首次创建时会被 Django 覆盖，用 update 还原备份中的时间
        manager.filter(pk=obj.pk).update(**force_fields)
    return obj


def _resolve(model, natural_field, old_id, source_index, label):
    if old_id is None:
        return None

    manager = _manager(model)
    row = source_index.get(old_id)
    if row is not None:
        key = row.get(natural_field)
        if key:
            obj = manager.filter(**{natural_field: key}).first()
            if obj is not None:
                return obj
            raise RestoreError(f'无法恢复：找不到{label}“{key}”，请确认备份文件完整')

    obj = manager.filter(pk=old_id).first()
    if obj is not None:
        return obj
    raise RestoreError(f'备份数据不完整：找不到关联的{label}（ID {old_id}）')


def _resolve_user(old_id, user_index):
    if old_id is None:
        return None
    row = user_index.get(old_id)
    username = row.get('username') if row else None
    if username:
        user = User.objects.filter(username=username).first()
        if user is not None:
            return user
    user = User.objects.filter(pk=old_id).first()
    if user is not None:
        return user
    raise RestoreError(f'备份数据不完整：找不到关联的用户（ID {old_id}）')


def _restore_items(
    rows, parent_model, parent_field, parent_natural_field, parent_index,
    parent_label, item_model, item_fields, fk_resolvers,
):
    """按父记录替换明细，避免对没有稳定业务主键的明细做模糊匹配。"""
    grouped = defaultdict(list)
    for row in rows:
        parent = _resolve(
            parent_model, parent_natural_field,
            row.get(f'{parent_field}_id'), parent_index, parent_label,
        )
        if parent is None:
            continue

        values = {
            field_name: _coerce(item_model, field_name, row[field_name])
            for field_name in item_fields if field_name in row
        }
        for field_name, resolver in fk_resolvers.items():
            values[field_name] = resolver(row.get(f'{field_name}_id'))
        grouped[parent.pk].append(item_model(**{parent_field: parent, **values}))

    for parent_id, items in grouped.items():
        item_model.objects.filter(**{f'{parent_field}_id': parent_id}).delete()
        item_model.objects.bulk_create(items)

    return sum(len(items) for items in grouped.values()), set(grouped)


def restore_backup_data(data):
    """恢复备份数据，返回各类型恢复条数；失败时整体回滚。"""
    if not isinstance(data, dict):
        raise RestoreError('无效的备份文件格式')

    sections = (
        'users', 'profiles', 'categories', 'projects', 'suppliers',
        'subcontractors', 'subcontract_categories', 'materials',
        'subcontract_lists', 'budgets', 'contracts', 'measurements',
        'settlements', 'material_plans', 'inbound_records',
        'purchase_plans', 'deliveries', 'budget_items', 'contract_items',
        'measurement_items', 'settlement_items', 'material_plan_items',
    )
    rows = {section: _rows(data, section) for section in sections}
    indexes = {section: _index(rows[section]) for section in sections}

    def fk(model, natural_field, section, label):
        return lambda old_id: _resolve(
            model, natural_field, old_id, indexes[section], label
        )

    def user_fk(old_id):
        return _resolve_user(old_id, indexes['users'])

    counts = {}
    touched_measurements = set()
    touched_settlements = set()
    touched_material_plans = set()

    with transaction.atomic():
        count = 0
        for row in rows['users']:
            username = (row.get('username') or '').strip()
            if not username:
                continue
            fields = {
                key: row[key] for key in (
                    'first_name', 'last_name', 'email', 'is_active', 'is_superuser',
                ) if key in row
            }
            user, created = User.objects.update_or_create(
                username=username, defaults=fields
            )
            if created:
                # 备份不含密码哈希，新建账号需管理员重置密码后才能登录
                user.set_unusable_password()
                user.save(update_fields=['password'])
            count += 1
        counts['users'] = count

        count = 0
        for row in rows['categories']:
            if _upsert(
                Category, 'code', row,
                ('name', 'remark', 'is_deleted', 'deleted_at'), {},
            ):
                count += 1
        counts['categories'] = count

        count = 0
        for row in rows['projects']:
            if _upsert(
                Project, 'code', row,
                (
                    'name', 'manager', 'start_date', 'end_date', 'budget',
                    'status', 'remark', 'created_at', 'is_deleted', 'deleted_at',
                ),
                {},
            ):
                count += 1
        counts['projects'] = count

        count = 0
        for row in rows['suppliers']:
            if _upsert(
                Supplier, 'code', row,
                (
                    'name', 'contact', 'phone', 'address', 'credit_rating',
                    'start_date', 'remark', 'created_at', 'is_deleted', 'deleted_at',
                ),
                {'main_type': fk(Category, 'code', 'categories', '材料分类')},
            ):
                count += 1
        counts['suppliers'] = count

        count = 0
        for row in rows['profiles']:
            user = _resolve_user(row.get('user_id'), indexes['users'])
            if user is None:
                continue
            role = row.get('role')
            if role not in dict(Profile.ROLE_CHOICES):
                role = 'management'
            Profile.objects.update_or_create(
                user=user,
                defaults={
                    'role': role,
                    'phone': row.get('phone') or '',
                    'supplier_info': _resolve(
                        Supplier, 'code',
                        row.get('supplier_info_id', row.get('supplier_id')),
                        indexes['suppliers'], '供应商',
                    ),
                },
            )
            count += 1
        counts['profiles'] = count

        count = 0
        for row in rows['subcontractors']:
            if _upsert(
                Subcontractor, 'code', row,
                (
                    'name', 'contact', 'phone', 'main_type', 'credit_rating',
                    'remark', 'created_at', 'is_deleted', 'deleted_at',
                ),
                {},
            ):
                count += 1
        counts['subcontractors'] = count

        count = 0
        for row in rows['subcontract_categories']:
            if _upsert(
                SubcontractCategory, 'category_code', row,
                ('category_name', 'remark', 'created_at', 'is_deleted', 'deleted_at'),
                {},
            ):
                count += 1
        counts['subcontract_categories'] = count

        count = 0
        for row in rows['materials']:
            if _upsert(
                Material, 'code', row,
                (
                    'name', 'spec', 'unit', 'standard_price', 'safety_stock',
                    'remark', 'created_at', 'is_deleted', 'deleted_at',
                ),
                {'category': fk(Category, 'code', 'categories', '材料分类')},
            ):
                count += 1
        counts['materials'] = count

        count = 0
        for row in rows['subcontract_lists']:
            if _upsert(
                SubcontractList, 'code', row,
                (
                    'name', 'construction_params', 'unit', 'reference_price',
                    'remark', 'created_at', 'is_deleted', 'deleted_at',
                ),
                {
                    'category': fk(
                        SubcontractCategory, 'category_code',
                        'subcontract_categories', '分包清单分类',
                    ),
                },
            ):
                count += 1
        counts['subcontract_lists'] = count

        count = 0
        for row in rows['budgets']:
            if _upsert(
                Budget, 'code', row,
                ('created_at', 'is_deleted', 'deleted_at'),
                {'project': fk(Project, 'code', 'projects', '项目')},
            ):
                count += 1
        counts['budgets'] = count

        count = 0
        for row in rows['contracts']:
            if _upsert(
                Contract, 'code', row,
                ('name', 'created_at', 'is_deleted', 'deleted_at'),
                {
                    'project': fk(Project, 'code', 'projects', '项目'),
                    'subcontractor': fk(
                        Subcontractor, 'code', 'subcontractors', '分包商'
                    ),
                },
            ):
                count += 1
        counts['contracts'] = count

        count = 0
        for row in rows['measurements']:
            code = row.get('code')
            if not code:
                continue
            contract = _resolve(
                Contract, 'code', row.get('contract_id'),
                indexes['contracts'], '合同',
            )
            if contract is None:
                raise RestoreError(f'进度计量 {code} 缺少关联合同')
            defaults = {
                field_name: _coerce(Measurement, field_name, row[field_name])
                for field_name in (
                    'period_start', 'period_end', 'previous_value',
                    'current_value', 'cumulative_value', 'created_at',
                    'is_deleted', 'deleted_at',
                ) if field_name in row
            }
            defaults.update({
                'contract': contract,
                'project': contract.project,
                'subcontractor': contract.subcontractor,
            })
            manager = Measurement.all_objects
            manager.update_or_create(code=code, defaults=defaults)
            force = {f: defaults[f] for f in AUTO_FIELDS if f in defaults}
            if force:
                manager.filter(code=code).update(**force)
            count += 1
        counts['measurements'] = count

        count = 0
        for row in rows['settlements']:
            code = row.get('code')
            if not code:
                continue
            contract = _resolve(
                Contract, 'code', row.get('contract_id'),
                indexes['contracts'], '合同',
            )
            if contract is None:
                raise RestoreError(f'分包结算 {code} 缺少关联合同')
            defaults = {
                field_name: _coerce(Settlement, field_name, row[field_name])
                for field_name in (
                    'period_start', 'period_end', 'measurement_value',
                    'deduction_reason', 'deduction_amount', 'final_amount',
                    'created_at', 'is_deleted', 'deleted_at',
                ) if field_name in row
            }
            defaults.update({
                'contract': contract,
                'project': contract.project,
                'subcontractor': contract.subcontractor,
            })
            manager = Settlement.all_objects
            manager.update_or_create(code=code, defaults=defaults)
            force = {f: defaults[f] for f in AUTO_FIELDS if f in defaults}
            if force:
                manager.filter(code=code).update(**force)
            count += 1
        counts['settlements'] = count

        count = 0
        for row in rows['material_plans']:
            if _upsert(
                MaterialPlan, 'plan_number', row,
                (
                    'plan_date', 'total_amount', 'description',
                    'created_at', 'updated_at', 'is_deleted', 'deleted_at',
                ),
                {
                    'project': fk(Project, 'code', 'projects', '项目'),
                    'created_by': user_fk,
                },
            ):
                count += 1
        counts['material_plans'] = count

        count = 0
        for row in rows['inbound_records']:
            if _upsert(
                InboundRecord, 'no', row,
                (
                    'date', 'quantity', 'unit_price', 'total_amount',
                    'batch_no', 'inspector', 'quality_status', 'spec',
                    'location', 'operate_time', 'remark',
                    'is_deleted', 'deleted_at',
                ),
                {
                    'project': fk(Project, 'code', 'projects', '项目'),
                    'material': fk(Material, 'code', 'materials', '材料'),
                    'supplier': fk(Supplier, 'code', 'suppliers', '供应商'),
                    'operator': user_fk,
                },
            ):
                count += 1
        counts['inbound_records'] = count

        count = 0
        for row in rows['purchase_plans']:
            if _upsert(
                PurchasePlan, 'no', row,
                (
                    'plan_quantity', 'inbound_quantity', 'quantity', 'spec',
                    'unit_price', 'total_amount', 'status', 'planned_date',
                    'remark', 'create_time', 'update_time',
                    'is_deleted', 'deleted_at',
                ),
                {
                    'project': fk(Project, 'code', 'projects', '项目'),
                    'material': fk(Material, 'code', 'materials', '材料'),
                    'material_plan': fk(
                        MaterialPlan, 'plan_number', 'material_plans', '材料计划'
                    ),
                    'supplier': fk(Supplier, 'code', 'suppliers', '供应商'),
                    'operator': user_fk,
                },
            ):
                count += 1
        counts['purchase_plans'] = count

        count = 0
        for row in rows['deliveries']:
            if _upsert(
                Delivery, 'no', row,
                (
                    'actual_quantity', 'actual_unit_price', 'actual_total_amount',
                    'shipping_method', 'plate_number', 'tracking_no', 'status',
                    'ship_time', 'remark', 'create_time',
                    'is_deleted', 'deleted_at',
                ),
                {
                    'purchase_plan': fk(
                        PurchasePlan, 'no', 'purchase_plans', '采购计划'
                    ),
                    'supplier': fk(Supplier, 'code', 'suppliers', '供应商'),
                },
            ):
                count += 1
        counts['deliveries'] = count

        subcontract_list_fk = fk(
            SubcontractList, 'code', 'subcontract_lists', '分包清单'
        )

        counts['budget_items'], _ = _restore_items(
            rows['budget_items'], Budget, 'budget', 'code', indexes['budgets'],
            '分包预算', BudgetItem,
            ('item_order', 'quantity', 'unit_price', 'total_amount'),
            {'subcontract_list': subcontract_list_fk},
        )
        counts['contract_items'], _ = _restore_items(
            rows['contract_items'], Contract, 'contract', 'code',
            indexes['contracts'], '分包合同', ContractItem,
            ('item_order', 'quantity', 'unit_price', 'total_amount'),
            {'subcontract_list': subcontract_list_fk},
        )
        counts['measurement_items'], touched_measurements = _restore_items(
            rows['measurement_items'], Measurement, 'measurement', 'code',
            indexes['measurements'], '进度计量', MeasurementItem,
            (
                'item_order', 'previous_quantity', 'current_quantity',
                'cumulative_quantity', 'unit_price', 'current_value',
            ),
            {'subcontract_list': subcontract_list_fk},
        )
        counts['settlement_items'], touched_settlements = _restore_items(
            rows['settlement_items'], Settlement, 'settlement', 'code',
            indexes['settlements'], '分包结算', SettlementItem,
            (
                'item_order', 'measurement_quantity', 'adjusted_quantity',
                'unit_price', 'final_value',
            ),
            {'subcontract_list': subcontract_list_fk},
        )
        counts['material_plan_items'], touched_material_plans = _restore_items(
            rows['material_plan_items'], MaterialPlan, 'material_plan',
            'plan_number', indexes['material_plans'], '材料计划',
            MaterialPlanItem,
            ('quantity', 'unit', 'unit_price', 'amount'),
            {'material': fk(Material, 'code', 'materials', '材料')},
        )

        # 明细恢复后重新汇总主表金额，保证与明细一致
        for measurement_id in touched_measurements:
            measurement = Measurement.all_objects.filter(pk=measurement_id).first()
            if measurement is None:
                continue
            total = MeasurementItem.objects.filter(
                measurement_id=measurement_id
            ).aggregate(t=Sum('current_value'))['t'] or Decimal('0')
            Measurement.all_objects.filter(pk=measurement_id).update(
                current_value=total,
                cumulative_value=(measurement.previous_value or Decimal('0')) + total,
            )

        for settlement_id in touched_settlements:
            settlement = Settlement.all_objects.filter(pk=settlement_id).first()
            if settlement is None:
                continue
            total = SettlementItem.objects.filter(
                settlement_id=settlement_id
            ).aggregate(t=Sum('final_value'))['t'] or Decimal('0')
            Settlement.all_objects.filter(pk=settlement_id).update(
                final_amount=total - (settlement.deduction_amount or Decimal('0'))
            )

        for plan_id in touched_material_plans:
            total = MaterialPlanItem.objects.filter(
                material_plan_id=plan_id
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            MaterialPlan.all_objects.filter(pk=plan_id).update(total_amount=total)

    return counts
