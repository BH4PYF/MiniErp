from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from inventory.models import MaterialPlan, MaterialPlanItem, Project, Material
from django.core.paginator import Paginator
import decimal

from .utils import purchase_plan_required, role_required

# 材料计划列表
@purchase_plan_required
def material_plan_list(request):
    # 生成新的计划编号（PLyyyymmdd000x格式）
    today = timezone.localtime(timezone.now()).strftime('%Y%m%d')
    last_plan = MaterialPlan.objects.filter(plan_number__startswith=f'PL{today}').order_by('-plan_number').first()
    if last_plan:
        last_seq = int(last_plan.plan_number[-4:])
        new_seq = last_seq + 1
    else:
        new_seq = 1
    new_plan_number = f'PL{today}{str(new_seq).zfill(4)}'
    
    # 获取筛选参数
    q = request.GET.get('q', '')
    project_id = request.GET.get('project', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    # 构建查询
    plans = MaterialPlan.objects.filter(is_deleted=False)
    
    # 应用筛选
    if q:
        plans = plans.filter(Q(plan_number__icontains=q) | Q(project__name__icontains=q))
    if project_id:
        plans = plans.filter(project_id=project_id)
    if start_date:
        plans = plans.filter(plan_date__gte=start_date)
    if end_date:
        plans = plans.filter(plan_date__lte=end_date)
    
    # 排序和分页
    plans = plans.order_by('-created_at')
    paginator = Paginator(plans, 10)
    page = request.GET.get('page')
    plans = paginator.get_page(page)
    
    # 获取所有材料和项目
    materials = Material.objects.filter(is_deleted=False)
    projects = Project.objects.filter(is_deleted=False)
    
    return render(request, 'inventory/material_plan_list.html', {
        'plans': plans,
        'new_plan_number': new_plan_number,
        'materials': materials,
        'projects': projects,
        'q': q,
        'project_id': project_id,
        'start_date': start_date,
        'end_date': end_date
    })

# 编辑材料计划（保留但重定向到列表页面）
@purchase_plan_required
def material_plan_edit(request, id):
    messages.info(request, '材料计划编辑功能已迁移到列表页面的内联操作')
    return redirect('material_plan_list')

# 创建材料计划（保留但重定向到列表页面）
@purchase_plan_required
def material_plan_create(request):
    messages.info(request, '材料计划创建功能已迁移到列表页面的内联操作')
    return redirect('material_plan_list')

# 删除材料计划
@purchase_plan_required
def material_plan_delete(request, id):
    plan = get_object_or_404(MaterialPlan, id=id, is_deleted=False)
    if request.method == 'POST':
        plan.delete()
        messages.success(request, '材料计划删除成功！')
        return redirect('material_plan_list')
    return redirect('material_plan_list')

# 材料计划详情
@purchase_plan_required
def material_plan_detail(request, id):
    plan = get_object_or_404(MaterialPlan, id=id, is_deleted=False)
    return render(request, 'inventory/material_plan_detail.html', {'plan': plan})

# 内联保存材料计划
@purchase_plan_required
def material_plan_save(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 获取表单数据
                plan_number = request.POST.get('plan_number')
                material_id = request.POST.get('material_id')
                quantity = request.POST.get('quantity')
                unit = request.POST.get('unit')
                standard_price = request.POST.get('standard_price')
                
                # 验证必填字段
                if not all([plan_number, material_id, quantity, unit, standard_price]):
                    messages.error(request, '请填写所有必填字段')
                    return redirect('material_plan_list')
                
                # 获取材料对象
                material = get_object_or_404(Material, id=material_id, is_deleted=False)
                
                # 解析数值
                try:
                    quantity = decimal.Decimal(quantity)
                    unit_price = decimal.Decimal(standard_price)
                except (ValueError, decimal.InvalidOperation):
                    messages.error(request, '数量或单价格式不正确')
                    return redirect('material_plan_list')
                
                # 检查是否已存在相同编号的计划
                existing_plan = MaterialPlan.objects.filter(plan_number=plan_number, is_deleted=False).first()
                if existing_plan:
                    # 使用现有计划
                    plan = existing_plan
                else:
                    # 创建新计划（默认选择第一个项目）
                    project = Project.objects.filter(is_deleted=False).first()
                    if not project:
                        messages.error(request, '请先创建项目')
                        return redirect('material_plan_list')
                    
                    plan = MaterialPlan.objects.create(
                        project=project,
                        plan_number=plan_number,
                        plan_date=timezone.now().date(),
                        created_by=request.user
                    )
                
                # 创建材料计划明细
                MaterialPlanItem.objects.create(
                    material_plan=plan,
                    material=material,
                    quantity=quantity,
                    unit=unit,
                    unit_price=unit_price
                )
                
                messages.success(request, '材料计划添加成功！')
        except Exception as e:
            messages.error(request, f'添加失败：{str(e)}')
    
    return redirect('material_plan_list')

# 导出材料计划
@role_required('admin', 'management')
def export_material_plans(request):
    """批量导出材料计划"""
    from django.db.models import Q
    from django.utils import timezone
    from .utils import create_excel_workbook, set_column_widths, make_excel_response, log_operation
    
    MAX_EXPORT_ROWS = 10000

    headers = [
        '计划编号', '项目', '计划日期', '计划总金额', '创建人', '创建时间'
    ]
    wb, ws, _ = create_excel_workbook('材料计划列表', headers, style='primary')

    plans = MaterialPlan.objects.select_related(
        'project', 'created_by'
    ).filter(is_deleted=False).order_by('-created_at')

    q = request.GET.get('q', '')
    project_id = request.GET.get('project', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    if q:
        plans = plans.filter(plan_number__icontains=q) | plans.filter(project__name__icontains=q)
    if project_id:
        plans = plans.filter(project_id=project_id)
    if start_date:
        plans = plans.filter(plan_date__gte=start_date)
    if end_date:
        plans = plans.filter(plan_date__lte=end_date)

    plans = plans[:MAX_EXPORT_ROWS]

    row = 2
    for p in plans:
        ws.cell(row=row, column=1, value=p.plan_number)
        ws.cell(row=row, column=2, value=f"{p.project.code} - {p.project.name}")
        ws.cell(row=row, column=3, value=str(p.plan_date))
        ws.cell(row=row, column=4, value=float(p.total_amount))
        ws.cell(row=row, column=5, value=p.created_by.username if p.created_by else '-')
        ws.cell(row=row, column=6, value=str(p.created_at.strftime('%Y-%m-%d %H:%M')))
        row += 1
    export_count = row - 2

    set_column_widths(ws, [15, 25, 12, 12, 12, 15])

    filename = f'材料计划_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

    log_operation(request.user, '材料计划', 'export', f'导出{export_count}条材料计划记录')
    return make_excel_response(wb, filename)

# 获取材料计划明细的API
@purchase_plan_required
def material_plan_items_api(request, plan_id):
    """获取材料计划的明细信息"""
    from django.http import JsonResponse
    plan = get_object_or_404(MaterialPlan, id=plan_id, is_deleted=False)
    items = plan.items.select_related('material').all()
    
    items_data = []
    for item in items:
        items_data.append({
            'id': item.id,
            'material_id': item.material.id,
            'material_name': item.material.name,
            'spec': item.material.spec,
            'unit': item.unit,
            'quantity': str(item.quantity),
            'unit_price': str(item.unit_price)
        })
    
    return JsonResponse({'items': items_data})
