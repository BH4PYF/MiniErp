from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q
from django.views.decorators.http import require_GET, require_POST
from django.core.paginator import Paginator
from django.utils import timezone

from ..models import Project, Material, PurchasePlan, Supplier, MaterialPlan
from ..services.dingtalk import DingTalkService
from .utils import (
    purchase_plan_required, role_required,
    log_operation, generate_no,
    parse_date, parse_positive_decimal, validate_required_fields,
    create_excel_workbook, set_column_widths, make_excel_response,
)


@purchase_plan_required
def purchase_plan_list(request):
    """采购计划列表"""
    plans = PurchasePlan.objects.select_related('project', 'material', 'operator', 'supplier').all()

    status = request.GET.get('status', '')
    project_id = request.GET.get('project', '')
    q = request.GET.get('q', '')

    if status:
        plans = plans.filter(status=status)
    if project_id:
        plans = plans.filter(project_id=project_id)
    if q:
        plans = plans.filter(Q(no__icontains=q) | Q(material__name__icontains=q))

    paginator = Paginator(plans, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    projects = Project.objects.all()
    materials = Material.objects.select_related('category').all()
    suppliers = Supplier.objects.all()
    # 获取材料计划及其明细
    material_plans = MaterialPlan.objects.select_related('project').prefetch_related('items__material').all()

    return render(request, 'inventory/purchase_plan_list.html', {
        'plans': page_obj,
        'projects': projects,
        'materials': materials,
        'suppliers': suppliers,
        'material_plans': material_plans,
        'status': status,
        'project_id': project_id,
        'q': q,
        'page_obj': page_obj,
    })


@purchase_plan_required
def purchase_plan_create(request):
    """创建采购计划"""
    # 下拉框数据
    projects = Project.objects.filter(is_deleted=False).order_by('name')
    materials = Material.objects.filter(is_deleted=False).order_by('name')
    suppliers = Supplier.objects.filter(is_deleted=False).order_by('name')
    
    return render(request, 'inventory/purchase_plan_create.html', {
        'projects': projects,
        'materials': materials,
        'suppliers': suppliers,
    })


from django.db.models import Sum

# 获取已入库数量的API
@purchase_plan_required
def get_inbound_quantity_api(request, project_id, material_id):
    """根据项目ID和材料ID获取已入库数量"""
    from django.http import JsonResponse
    from ..models import InboundRecord
    # 获取该项目该材料的已入库数量
    inbound_quantity = InboundRecord.objects.filter(
        project_id=project_id,
        material_id=material_id,
        is_deleted=False
    ).aggregate(total=Sum('quantity'))['total'] or 0
    return JsonResponse({'inbound_quantity': str(inbound_quantity)})

@purchase_plan_required
def purchase_plan_save(request):
    """保存采购计划"""
    if request.method == 'POST':
        pk = request.POST.get('id')
        if pk:
            # 编辑现有采购计划
            try:
                obj = PurchasePlan.objects.get(pk=pk)
            except PurchasePlan.DoesNotExist:
                return JsonResponse({'success': False, 'message': '采购计划不存在'}, status=404)
            
            # 只有审批中和采购中的采购计划可以编辑
            if obj.status not in [PurchasePlan.STATUS_PENDING, PurchasePlan.STATUS_PURCHASING]:
                status_display = obj.get_status_display()
                return JsonResponse({
                    'success': False, 
                    'message': f'当前状态为"{status_display}"的采购计划不可编辑，只有审批中或采购中的采购计划可以修改'
                }, status=400)
            
            action = 'update'
        else:
            obj = PurchasePlan()
            obj.operator = request.user
            action = 'create'

        project_id = request.POST.get('project_id')
        material_id = request.POST.get('material_id')
        material_plan_id = request.POST.get('material_plan_id', '').strip()
        supplier_id = request.POST.get('supplier_id', '').strip()
        err = validate_required_fields(request.POST, {
            'project_id': '请选择所属项目',
            'material_id': '请选择材料',
            'supplier_id': '请选择供应商',
        })
        if err:
            return JsonResponse({'error': err}, status=400)
        obj.project_id = project_id
        obj.material_id = material_id
        obj.material_plan_id = material_plan_id if material_plan_id else None
        obj.supplier_id = supplier_id
        # 从Material模型中获取规格和标准单价
        if material_id:
            try:
                material = Material.objects.get(pk=material_id)
                # 确保规格不为空
                if not material.spec:
                    return JsonResponse({'error': '材料规格信息不完整，请在材料档案中完善规格信息'}, status=400)
                obj.spec = material.spec
                obj.unit_price = material.standard_price
            except Material.DoesNotExist:
                return JsonResponse({'error': '材料不存在'}, status=400)
        quantity, err = parse_positive_decimal(request.POST.get('quantity'), '采购数量')
        if err:
            return JsonResponse({'error': err}, status=400)
        obj.quantity = quantity
        # 计划采购日期设置为当前日期
        obj.planned_date = timezone.now().date()
        # 设置计划数量和已入库数量
        plan_quantity = request.POST.get('plan_quantity', '0')
        obj.plan_quantity = Decimal(plan_quantity) if plan_quantity else Decimal('0')
        inbound_quantity = request.POST.get('inbound_quantity', '0')
        obj.inbound_quantity = Decimal(inbound_quantity) if inbound_quantity else Decimal('0')
        # 设置操作员为当前用户
        obj.operator = request.user
        VALID_STATUSES = {c[0] for c in PurchasePlan.STATUS_CHOICES}
        status = request.POST.get('status', PurchasePlan.STATUS_PENDING)
        if status not in VALID_STATUSES:
            status = PurchasePlan.STATUS_PENDING
        obj.status = status
        obj.remark = request.POST.get('remark', '')

        with transaction.atomic():
            if action == 'create':
                obj.no = generate_no('PP', PurchasePlan)
            obj.save()

        log_operation(request.user, '采购计划', action,
                      f'{"新增" if action == "create" else "修改"}采购计划 {obj.no} 材料:{obj.material.name} 数量:{obj.quantity}', obj.no)
        if action == 'create':
            DingTalkService.notify_if_enabled(
                'purchase_plan_created',
                plan_no=obj.no,
                material_name=str(obj.material.name),
                quantity=str(obj.quantity),
                project_name=str(obj.project.name),
                supplier_name=str(obj.supplier.name) if obj.supplier else '未知',
                url=f'{request.scheme}://{request.get_host()}/purchase-plans/',
            )
        return JsonResponse({'success': True, 'message': '保存成功'})
    return redirect('purchase_plan_list')


@role_required('admin', 'management')
@require_POST
def purchase_plan_delete(request, pk):
    """删除采购计划（硬删除）"""
    obj = get_object_or_404(PurchasePlan, pk=pk)
    
    if request.method == 'POST':
        # 只允许删除审批中和采购中的采购计划
        if obj.status not in [PurchasePlan.STATUS_PENDING, PurchasePlan.STATUS_PURCHASING]:
            return JsonResponse({'success': False, 'message': '只有审批中和采购中的采购计划可以删除'}, status=400)
        
        no = obj.no
        obj.hard_delete()
        log_operation(request.user, '采购计划', 'delete', f'删除采购计划 {no}', no)
        
        return JsonResponse({'success': True, 'message': '删除成功'})
    
    return JsonResponse({'success': False, 'message': '方法不允许'}, status=405)


@purchase_plan_required
def export_purchase_plans(request):
    """批量导出采购计划"""
    MAX_EXPORT_ROWS = 10000

    headers = [
        '计划编号', '项目', '材料', '规格', '单位',
        '数量', '供应商', '预计金额', '计划日期', '状态'
    ]
    wb, ws, _ = create_excel_workbook('采购计划列表', headers, style='primary')

    plans = PurchasePlan.objects.select_related(
        'project', 'material', 'operator', 'supplier'
    ).all().order_by('-planned_date', '-create_time')

    status = request.GET.get('status', '')
    project_id = request.GET.get('project', '')
    q = request.GET.get('q', '')

    if status:
        plans = plans.filter(status=status)
    if project_id:
        plans = plans.filter(project_id=project_id)
    if q:
        plans = plans.filter(Q(no__icontains=q) | Q(material__name__icontains=q))

    plans = plans[:MAX_EXPORT_ROWS]

    row = 2
    for p in plans:
        status_display = dict(PurchasePlan.STATUS_CHOICES).get(p.status, p.status)

        ws.cell(row=row, column=1, value=p.no)
        ws.cell(row=row, column=2, value=f"{p.project.code} - {p.project.name}")
        ws.cell(row=row, column=3, value=p.material.name)
        ws.cell(row=row, column=4, value=p.spec or '-')
        ws.cell(row=row, column=5, value=p.material.unit)
        ws.cell(row=row, column=6, value=float(p.quantity))
        ws.cell(row=row, column=7, value=p.supplier.name if p.supplier else '-')
        ws.cell(row=row, column=8, value=float(p.total_amount))
        ws.cell(row=row, column=9, value=str(p.planned_date) if p.planned_date else '-')
        ws.cell(row=row, column=10, value=status_display)
        row += 1
    export_count = row - 2

    set_column_widths(ws, [15, 25, 20, 15, 8, 10, 15, 12, 12, 10])

    filename = f'采购计划_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

    log_operation(request.user, '采购计划', 'export', f'导出{export_count}条采购计划记录')
    return make_excel_response(wb, filename)


@role_required('admin', 'management')
@require_POST
def purchase_plan_approve(request, pk):
    """审批采购计划：从审批中变为采购中"""
    obj = get_object_or_404(PurchasePlan, pk=pk)
    if obj.status != 'pending':
        return JsonResponse({'error': '只有审批中的采购计划才能审批'}, status=400)
    if not obj.supplier_id:
        return JsonResponse({'error': '请选择供应商'}, status=400)
    obj.status = PurchasePlan.STATUS_PURCHASING
    obj.save()
    log_operation(request.user, '采购计划', 'update',
                  f'审批通过采购计划 {obj.no} 材料:{obj.material.name}', obj.no)
    return JsonResponse({'success': True, 'message': '审批通过'})


@purchase_plan_required
@require_GET
def purchase_plan_detail_api(request, pk):
    """采购计划详情API"""
    obj = get_object_or_404(PurchasePlan, pk=pk)
    data = {
        'id': obj.pk,
        'no': obj.no,
        'project_id': obj.project_id,
        'material_id': obj.material_id,
        'material_plan_id': obj.material_plan_id,
        'supplier_id': obj.supplier_id,
        'spec': obj.spec,
        'quantity': str(obj.quantity),
        'unit_price': str(obj.unit_price),
        'planned_date': str(obj.planned_date or ''),
        'status': obj.status,
        'remark': obj.remark,
    }
    return JsonResponse(data)
