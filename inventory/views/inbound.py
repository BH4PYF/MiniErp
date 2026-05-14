from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_GET, require_POST
from django.core.paginator import Paginator
from django.db.models import Q

from ..models import Project, Material, Supplier, InboundRecord
from ..services.dingtalk import DingTalkService
from .utils import (
    admin_required, inventory_required,
    is_ajax_request, log_operation, generate_no, parse_date, parse_positive_decimal,
    validate_required_fields,
)


@inventory_required
def inbound_list(request):
    records = InboundRecord.objects.select_related('project', 'material', 'supplier', 'operator').all()
    date_from = parse_date(request.GET.get('date_from', ''))
    date_to = parse_date(request.GET.get('date_to', ''))
    
    project_id = request.GET.get('project', '')
    material_id = request.GET.get('material', '')
    supplier_id = request.GET.get('supplier', '')
    
    if date_from:
        records = records.filter(date__gte=date_from)
    if date_to:
        records = records.filter(date__lte=date_to)
    
    if project_id:
        records = records.filter(project_id=project_id)
    if material_id:
        records = records.filter(material_id=material_id)
    if supplier_id:
        records = records.filter(supplier_id=supplier_id)

    paginator = Paginator(records, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    projects = Project.objects.only('id', 'code', 'name').all()
    materials = Material.objects.select_related('category').only(
        'id', 'code', 'name', 'spec', 'category__name',
    ).all()
    suppliers = Supplier.objects.only('id', 'code', 'name').all()
    return render(request, 'inventory/inbound_list.html', {
        'records': page_obj, 'projects': projects, 'materials': materials,
        'suppliers': suppliers, 'date_from': date_from, 'date_to': date_to,
        'selected_project': project_id, 'selected_material': material_id, 'selected_supplier': supplier_id,
        'page_obj': page_obj,
    })


@inventory_required
def inbound_save(request):
    if request.method == 'POST':
        pk = request.POST.get('id')
        if pk:
            obj = get_object_or_404(InboundRecord, pk=pk)
            action = 'update'
        else:
            obj = InboundRecord()
            obj.operator = request.user
            action = 'create'
        err = validate_required_fields(request.POST, {
            'project_id': '请选择所属项目',
            'material_id': '请选择材料',
            'supplier_id': '请选择供应商',
        })
        if err:
            return JsonResponse({'error': err}, status=400)
        project_id = request.POST.get('project_id')
        obj.project_id = project_id
        obj.material_id = request.POST.get('material_id')
        parsed_date = parse_date(request.POST.get('date'))
        if not parsed_date:
            return JsonResponse({'error': '入库日期格式不正确，请使用 YYYY-MM-DD 格式'}, status=400)
        obj.date = parsed_date
        quantity, err = parse_positive_decimal(request.POST.get('quantity'), '入库数量')
        if err:
            return JsonResponse({'error': err}, status=400)
        obj.quantity = quantity
        unit_price, err = parse_positive_decimal(request.POST.get('unit_price'), '单价', allow_zero=True)
        if err:
            return JsonResponse({'error': err}, status=400)
        obj.unit_price = unit_price
        obj.supplier_id = request.POST.get('supplier_id')
        obj.batch_no = request.POST.get('batch_no', '')
        obj.spec = request.POST.get('spec', '')
        obj.remark = request.POST.get('remark', '')
        try:
            obj.clean()
        except ValidationError as e:
            errors = []
            for field, field_errors in e.message_dict.items():
                errors.extend(field_errors)
            return JsonResponse({'error': '；'.join(errors)}, status=400)
        try:
            with transaction.atomic():
                if action == 'create':
                    obj.no = generate_no('IN')
                obj.save()
        except ValidationError as e:
            if hasattr(e, 'message_dict'):
                errors = []
                for field_errors in e.message_dict.values():
                    errors.extend(field_errors)
                return JsonResponse({'error': '；'.join(errors)}, status=400)
            return JsonResponse({'error': str(e.message)}, status=400)
        log_operation(request.user, '入库管理', action,
                      f'{"新增" if action == "create" else "修改"}入库单 {obj.no} 材料:{obj.material.name} 数量:{obj.quantity}', obj.no)
        if action == 'create':
            DingTalkService.notify_if_enabled(
                'inbound_created',
                inbound_no=obj.no,
                material_name=str(obj.material.name),
                quantity=str(obj.quantity),
                project_name=str(obj.project.name),
                url=f'{request.scheme}://{request.get_host()}/inbound/',
            )
        if is_ajax_request(request):
            return JsonResponse({'success': True, 'message': '保存成功'})
        return redirect('inbound_list')
    return redirect('inbound_list')


@admin_required
@require_POST
def inbound_delete(request, pk):
    obj = get_object_or_404(InboundRecord, pk=pk)
    no = obj.no
    obj.delete()
    log_operation(request.user, '入库管理', 'delete', f'删除入库单 {no}', no)
    return JsonResponse({'success': True})


@inventory_required
@require_GET
def inbound_detail_api(request, pk):
    obj = get_object_or_404(InboundRecord, pk=pk)
    data = {
        'id': obj.pk, 'no': obj.no, 'project_id': obj.project_id,
        'material_id': obj.material_id, 'date': str(obj.date),
        'quantity': str(obj.quantity), 'unit_price': str(obj.unit_price),
        'total_amount': str(obj.total_amount), 'supplier_id': obj.supplier_id,
        'batch_no': obj.batch_no,
        'spec': obj.spec, 'unit': obj.material.unit if obj.material else '',
        'remark': obj.remark,
    }
    return JsonResponse(data)
