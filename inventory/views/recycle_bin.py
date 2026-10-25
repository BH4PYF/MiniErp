from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from ..models import (
    Budget, Category, Contract, Delivery, InboundRecord, Material,
    MaterialPlan, Measurement, Project, PurchasePlan, Settlement,
    SubcontractCategory, SubcontractList, Subcontractor, Supplier,
)
from .utils import admin_required, log_operation

# (URL 参数, 模型, 显示名, 搜索字段)
RECYCLE_MODELS = (
    ('project', Project, '项目', ('code', 'name', 'manager')),
    ('material', Material, '材料', ('code', 'name', 'spec')),
    ('category', Category, '材料分类', ('code', 'name')),
    ('supplier', Supplier, '供应商', ('code', 'name', 'contact', 'phone')),
    ('subcontractor', Subcontractor, '分包商', ('code', 'name', 'contact', 'phone')),
    ('subcontract_category', SubcontractCategory, '分包清单分类', ('category_code', 'category_name')),
    ('subcontract_list', SubcontractList, '分包清单', ('code', 'name', 'construction_params')),
    ('budget', Budget, '分包预算', ('code',)),
    ('contract', Contract, '分包合同', ('code', 'name')),
    ('measurement', Measurement, '进度计量', ('code',)),
    ('settlement', Settlement, '分包结算', ('code',)),
    ('material_plan', MaterialPlan, '材料计划', ('plan_number', 'description')),
    ('inbound_record', InboundRecord, '入库记录', ('no', 'batch_no', 'spec')),
    ('purchase_plan', PurchasePlan, '采购计划', ('no', 'spec')),
    ('delivery', Delivery, '发货单', ('no', 'plate_number', 'tracking_no')),
)

MODEL_MAP = {
    key: (model, label, search_fields)
    for key, model, label, search_fields in RECYCLE_MODELS
}

# 恢复前必须保证上级档案未删除，否则恢复出来的数据在列表里看不到
DEPENDENCIES = {
    'material': (('category', '材料分类'),),
    'subcontract_list': (('category', '分包清单分类'),),
    'budget': (('project', '项目'),),
    'contract': (('project', '项目'), ('subcontractor', '分包商')),
    'measurement': (
        ('contract', '合同'), ('project', '项目'), ('subcontractor', '分包商'),
    ),
    'settlement': (
        ('contract', '合同'), ('project', '项目'), ('subcontractor', '分包商'),
    ),
    'inbound_record': (
        ('project', '项目'), ('material', '材料'), ('supplier', '供应商'),
    ),
    'purchase_plan': (
        ('project', '项目'), ('material', '材料'),
        ('supplier', '供应商'), ('material_plan', '材料计划'),
    ),
    'delivery': (('purchase_plan', '采购计划'), ('supplier', '供应商')),
    'material_plan': (('project', '项目'),),
}


def _blocking_dependency(model_key, obj):
    for attr, label in DEPENDENCIES.get(model_key, ()):
        dependency = getattr(obj, attr, None)
        if dependency is not None and getattr(dependency, 'is_deleted', False):
            return f'无法恢复：所属{label}“{dependency}”仍在回收站，请先恢复{label}'
    return None


def _related_no(obj):
    for attr in ('code', 'no', 'plan_number', 'category_code'):
        value = getattr(obj, attr, '')
        if value:
            return str(value)
    return str(obj.pk)


@admin_required
@require_GET
def recycle_bin(request):
    q = request.GET.get('q', '').strip()
    selected_key = request.GET.get('model', '')

    counts = [
        (key, label, model.all_objects.filter(is_deleted=True).count())
        for key, model, label, _ in RECYCLE_MODELS
    ]
    total_deleted = sum(count for _, _, count in counts)

    if selected_key not in MODEL_MAP:
        selected_key = next(
            (key for key, _, count in counts if count), ''
        )

    page_obj = None
    if selected_key:
        model, _, search_fields = MODEL_MAP[selected_key]
        queryset = model.all_objects.filter(is_deleted=True).order_by('-deleted_at', '-pk')
        if q:
            condition = Q()
            for field in search_fields:
                condition |= Q(**{f'{field}__icontains': q})
            queryset = queryset.filter(condition)

        page_obj = Paginator(queryset, 20).get_page(request.GET.get('page'))

    return render(request, 'inventory/recycle_bin.html', {
        'counts': counts,
        'total_deleted': total_deleted,
        'selected_key': selected_key,
        'selected_label': MODEL_MAP[selected_key][1] if selected_key else '',
        'page_obj': page_obj,
        'q': q,
    })


@admin_required
@require_POST
def recycle_bin_restore(request, model_key, pk):
    entry = MODEL_MAP.get(model_key)
    if entry is None:
        return JsonResponse({'error': '未知数据类型'}, status=404)

    model, label, _ = entry
    obj = get_object_or_404(model.all_objects, pk=pk, is_deleted=True)

    blocking = _blocking_dependency(model_key, obj)
    if blocking:
        return JsonResponse({'error': blocking}, status=400)

    obj.restore()
    log_operation(
        request.user, '回收站', 'update',
        f'恢复{label} {obj}', _related_no(obj),
    )
    return JsonResponse({'success': True, 'message': f'{label}已恢复'})
