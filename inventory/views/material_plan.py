from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
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
    # 考虑所有记录（包括已软删除的）
    last_plan = MaterialPlan.objects.all().filter(plan_number__startswith=f'PL{today}').order_by('-plan_number').first()
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
    
    # 计算每个材料计划的入库总额和整体进度
    from inventory.models import InboundRecord
    from django.db.models import Sum
    for plan in plans:
        total_plan_amount = 0
        total_inbound_amount = 0
        
        for item in plan.items.all():
            # 计算该项目该材料的入库总量
            inbound_total = InboundRecord.objects.filter(
                project=plan.project,
                material=item.material,
                is_deleted=False
            ).aggregate(total=Sum('quantity'))['total'] or 0
            item.inbound_total = inbound_total
            
            # 计算材料项的进度百分比
            if item.quantity > 0:
                item.progress = min(100, int((inbound_total / item.quantity) * 100))
            else:
                item.progress = 0
            
            # 累加计划总额和入库总额
            total_plan_amount += item.amount
            total_inbound_amount += inbound_total * item.unit_price
        
        # 设置材料计划的总金额和入库总额
        plan.total_amount = total_plan_amount
        plan.total_inbound_amount = total_inbound_amount
        
        # 计算整体进度
        if total_plan_amount > 0:
            plan.overall_progress = min(100, int((total_inbound_amount / total_plan_amount) * 100))
        else:
            plan.overall_progress = 0
    
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

# 编辑材料计划
@purchase_plan_required
def material_plan_edit(request, id):
    plan = get_object_or_404(MaterialPlan, id=id, is_deleted=False)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 获取表单数据
                project_id = request.POST.get('project')
                item_orders = request.POST.getlist('item_order')
                materials = request.POST.getlist('material')
                quantities = request.POST.getlist('quantity')
                
                # 验证必填字段
                if not project_id:
                    messages.error(request, '请选择项目')
                    return redirect('material_plan_edit', id=id)
                
                if not materials or not quantities:
                    messages.error(request, '请至少添加一个材料')
                    return redirect('material_plan_edit', id=id)
                
                # 获取项目对象
                project = get_object_or_404(Project, id=project_id, is_deleted=False)
                
                # 更新材料计划
                plan.project = project
                plan.save()
                
                # 删除原有材料计划明细
                plan.items.all().delete()
                
                # 创建新的材料计划明细
                for i, (item_order, material_id, quantity) in enumerate(zip(item_orders, materials, quantities)):
                    if material_id and quantity:
                        # 获取材料对象
                        material = get_object_or_404(Material, id=material_id, is_deleted=False)
                        
                        # 解析数值
                        try:
                            quantity = decimal.Decimal(quantity)
                        except (ValueError, decimal.InvalidOperation):
                            messages.error(request, f'第{i+1}行数量格式不正确')
                            return redirect('material_plan_edit', id=id)
                        
                        # 创建材料计划项
                        MaterialPlanItem.objects.create(
                            material_plan=plan,
                            material=material,
                            quantity=quantity,
                            unit=material.unit,
                            unit_price=material.standard_price
                        )
                
                messages.success(request, '材料计划编辑成功！')
                return redirect('material_plan_list')
        except Exception as e:
            messages.error(request, f'编辑失败：{str(e)}')
            return redirect('material_plan_edit', id=id)
    
    # GET请求，渲染编辑页面
    materials = Material.objects.filter(is_deleted=False)
    projects = Project.objects.filter(is_deleted=False)
    
    return render(request, 'inventory/material_plan_edit.html', {
        'plan': plan,
        'materials': materials,
        'projects': projects
    })

# 创建材料计划
@purchase_plan_required
def material_plan_create(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 生成新的计划编号（PLyyyymmdd000x格式）
                today = timezone.localtime(timezone.now()).strftime('%Y%m%d')
                # 考虑所有记录（包括已软删除的）
                last_plan = MaterialPlan.objects.all().filter(plan_number__startswith=f'PL{today}').order_by('-plan_number').first()
                if last_plan:
                    last_seq = int(last_plan.plan_number[-4:])
                    new_seq = last_seq + 1
                else:
                    new_seq = 1
                new_plan_number = f'PL{today}{str(new_seq).zfill(4)}'
                
                # 获取表单数据
                project_id = request.POST.get('project')
                item_orders = request.POST.getlist('item_order')
                materials = request.POST.getlist('material')
                quantities = request.POST.getlist('quantity')
                
                # 验证必填字段
                if not project_id:
                    messages.error(request, '请选择项目')
                    return redirect('material_plan_create')
                
                if not materials or not quantities:
                    messages.error(request, '请至少添加一个材料')
                    return redirect('material_plan_create')
                
                # 获取项目对象
                project = get_object_or_404(Project, id=project_id, is_deleted=False)
                
                # 创建材料计划
                plan = MaterialPlan.objects.create(
                    project=project,
                    plan_number=new_plan_number,
                    plan_date=timezone.now().date(),
                    created_by=request.user
                )
                
                # 创建材料计划明细
                for i, (item_order, material_id, quantity) in enumerate(zip(item_orders, materials, quantities)):
                    if material_id and quantity:
                        # 获取材料对象
                        material = get_object_or_404(Material, id=material_id, is_deleted=False)
                        
                        # 解析数值
                        try:
                            quantity = decimal.Decimal(quantity)
                        except (ValueError, decimal.InvalidOperation):
                            messages.error(request, f'第{i+1}行数量格式不正确')
                            return redirect('material_plan_create')
                        
                        # 创建材料计划项
                        MaterialPlanItem.objects.create(
                            material_plan=plan,
                            material=material,
                            quantity=quantity,
                            unit=material.unit,
                            unit_price=material.standard_price
                        )
                
                messages.success(request, '材料计划创建成功！')
                return redirect('material_plan_list')
        except Exception as e:
            messages.error(request, f'创建失败：{str(e)}')
            return redirect('material_plan_create')
    
    # GET请求，渲染创建页面
    # 生成新的计划编号（PLyyyymmdd000x格式）
    today = timezone.localtime(timezone.now()).strftime('%Y%m%d')
    # 考虑所有记录（包括已软删除的）
    last_plan = MaterialPlan.objects.all().filter(plan_number__startswith=f'PL{today}').order_by('-plan_number').first()
    if last_plan:
        last_seq = int(last_plan.plan_number[-4:])
        new_seq = last_seq + 1
    else:
        new_seq = 1
    new_plan_number = f'PL{today}{str(new_seq).zfill(4)}'
    
    materials = Material.objects.filter(is_deleted=False)
    projects = Project.objects.filter(is_deleted=False)
    
    return render(request, 'inventory/material_plan_create.html', {
        'materials': materials,
        'projects': projects,
        'new_plan_number': new_plan_number
    })

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
    # 预加载材料计划项
    plan = get_object_or_404(MaterialPlan.objects.prefetch_related('items__material'), id=id, is_deleted=False)
    
    # 计算每个材料计划项的入库总量和进度
    from inventory.models import InboundRecord
    from django.db.models import Sum
    
    # 为计划项添加入库总量和进度属性
    items_with_progress = []
    for item in plan.items.all():
        # 计算该项目该材料的入库总量
        inbound_total = InboundRecord.objects.filter(
            project=plan.project,
            material=item.material,
            is_deleted=False
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # 计算材料项的进度百分比
        if item.quantity > 0:
            progress = min(100, int((inbound_total / item.quantity) * 100))
        else:
            progress = 0
        
        # 将计算结果添加到item对象
        item.inbound_total = inbound_total
        item.progress = progress
        items_with_progress.append(item)
    
    # 将处理后的items设置回plan对象
    plan.items_list = items_with_progress
    
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
                
                # 检查是否已存在相同编号的计划（包括已软删除的）
                existing_plan = MaterialPlan.objects.all().filter(plan_number=plan_number).first()
                if existing_plan and not existing_plan.is_deleted:
                    # 使用现有计划
                    plan = existing_plan
                elif existing_plan and existing_plan.is_deleted:
                    # 如果计划已删除，生成新的编号
                    today = timezone.localtime(timezone.now()).strftime('%Y%m%d')
                    # 考虑所有记录（包括已软删除的）
                    last_plan = MaterialPlan.objects.all().filter(plan_number__startswith=f'PL{today}').order_by('-plan_number').first()
                    if last_plan:
                        last_seq = int(last_plan.plan_number[-4:])
                        new_seq = last_seq + 1
                    else:
                        new_seq = 1
                    new_plan_number = f'PL{today}{str(new_seq).zfill(4)}'
                    
                    # 创建新计划（默认选择第一个项目）
                    project = Project.objects.filter(is_deleted=False).first()
                    if not project:
                        messages.error(request, '请先创建项目')
                        return redirect('material_plan_list')
                    
                    plan = MaterialPlan.objects.create(
                        project=project,
                        plan_number=new_plan_number,
                        plan_date=timezone.now().date(),
                        created_by=request.user
                    )
                else:
                    # 生成新的计划编号（PLyyyymmdd000x格式）
                    today = timezone.localtime(timezone.now()).strftime('%Y%m%d')
                    # 考虑所有记录（包括已软删除的）
                    last_plan = MaterialPlan.objects.all().filter(plan_number__startswith=f'PL{today}').order_by('-plan_number').first()
                    if last_plan:
                        last_seq = int(last_plan.plan_number[-4:])
                        new_seq = last_seq + 1
                    else:
                        new_seq = 1
                    new_plan_number = f'PL{today}{str(new_seq).zfill(4)}'
                    
                    # 创建新计划（默认选择第一个项目）
                    project = Project.objects.filter(is_deleted=False).first()
                    if not project:
                        messages.error(request, '请先创建项目')
                        return redirect('material_plan_list')
                    
                    plan = MaterialPlan.objects.create(
                        project=project,
                        plan_number=new_plan_number,
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

# 根据项目ID获取材料计划明细的API
@purchase_plan_required
def material_plan_items_by_project_api(request, project_id):
    """根据项目ID获取材料计划明细信息"""
    from django.http import JsonResponse
    # 获取该项目的所有材料计划
    plans = MaterialPlan.objects.filter(project_id=project_id, is_deleted=False)
    items_data = []
    for plan in plans:
        items = plan.items.select_related('material').all()
        for item in items:
            items_data.append({
                'plan_id': plan.id,
                'plan_number': plan.plan_number,
                'material_id': item.material.id,
                'material_name': item.material.name,
                'spec': item.material.spec,
                'unit': item.unit,
                'quantity': str(item.quantity)
            })
    
    return JsonResponse({'items': items_data})
