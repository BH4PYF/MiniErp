from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from inventory.models import Budget, BudgetItem, Project, SubcontractList
from inventory.services.rate_limit_service import check_rate_limit
from .utils import create_excel_workbook, set_column_widths, make_excel_response


def budget_list(request):
    """分包预算列表"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    # 获取筛选参数
    selected_project = request.GET.get('project')
    
    # 构建查询集
    budgets = Budget.objects.all()
    
    # 应用筛选
    if selected_project:
        budgets = budgets.filter(project_id=selected_project)
    
    # 获取所有项目和分包商用于筛选
    projects = Project.objects.all()
    
    return render(request, 'inventory/budget_list.html', {
        'budgets': budgets,
        'projects': projects,
        'selected_project': selected_project
    })


def budget_create(request):
    """创建分包预算"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    projects = Project.objects.all()
    
    if request.method == 'POST':
        # 检查速率限制
        if not check_rate_limit(request, 'budget_create', limit=5, window=60):
            messages.error(request, '操作过于频繁，请稍后再试')
            return redirect('budget_list')
        
        try:
            # 生成自动编号
            last_budget = Budget.objects.order_by('-code').first()
            if last_budget:
                last_code = int(last_budget.code.split('-')[-1])
                new_code = f'B-{str(last_code + 1).zfill(4)}'
            else:
                new_code = 'B-0001'
            
            with transaction.atomic():
                budget = Budget(
                    code=new_code,
                    project_id=request.POST.get('project')
                )
                budget.save()
                
                # 处理预算清单
                item_orders = request.POST.getlist('item_order')
                subcontract_list_ids = request.POST.getlist('subcontract_list')
                quantities = request.POST.getlist('quantity')
                unit_prices = request.POST.getlist('unit_price')
                
                for i, item_order in enumerate(item_orders):
                    if item_order and subcontract_list_ids[i] and quantities[i] and unit_prices[i]:
                        BudgetItem.objects.create(
                            budget=budget,
                            item_order=item_order,
                            subcontract_list_id=subcontract_list_ids[i],
                            quantity=Decimal(quantities[i]),
                            unit_price=Decimal(unit_prices[i])
                        )
                
            messages.success(request, '分包预算创建成功')
            return redirect('budget_list')
        except Exception as e:
            messages.error(request, f'创建失败: {str(e)}')
    
    subcontract_lists = SubcontractList.objects.all()
    return render(request, 'inventory/budget_create.html', {'projects': projects, 'subcontract_lists': subcontract_lists})


def budget_edit(request, pk):
    """编辑分包预算"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    budget = get_object_or_404(Budget, pk=pk)
    projects = Project.objects.all()
    subcontract_lists = SubcontractList.objects.all()
    
    if request.method == 'POST':
        # 检查速率限制
        if not check_rate_limit(request, 'budget_edit', limit=5, window=60):
            messages.error(request, '操作过于频繁，请稍后再试')
            return redirect('budget_list')
        
        try:
            with transaction.atomic():
                budget.project_id = request.POST.get('project')
                budget.save()
                
                # 删除旧的预算清单
                budget.budget_items.all().delete()
                
                # 处理新的预算清单
                item_orders = request.POST.getlist('item_order')
                subcontract_list_ids = request.POST.getlist('subcontract_list')
                quantities = request.POST.getlist('quantity')
                unit_prices = request.POST.getlist('unit_price')
                
                for i, item_order in enumerate(item_orders):
                    if item_order and subcontract_list_ids[i] and quantities[i] and unit_prices[i]:
                        BudgetItem.objects.create(
                            budget=budget,
                            item_order=item_order,
                            subcontract_list_id=subcontract_list_ids[i],
                            quantity=Decimal(quantities[i]),
                            unit_price=Decimal(unit_prices[i])
                        )
                
            messages.success(request, '分包预算更新成功')
            return redirect('budget_list')
        except Exception as e:
            messages.error(request, f'更新失败: {str(e)}')
    
    return render(request, 'inventory/budget_edit.html', {
        'budget': budget, 
        'projects': projects, 
        'subcontract_lists': subcontract_lists
    })


def budget_delete(request, pk):
    """删除分包预算"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    budget = get_object_or_404(Budget, pk=pk)
    
    if request.method == 'POST':
        try:
            if budget.budget_items.exists():
                messages.error(request, f'预算"{budget.code}"已有预算清单，不可删除')
            else:
                budget.delete()
                messages.success(request, '分包预算删除成功')
        except Exception as e:
            messages.error(request, f'删除失败: {str(e)}')
        return redirect('budget_list')
    
    return redirect('budget_list')


def budget_detail(request, pk):
    """分包预算详情"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    budget = get_object_or_404(Budget, pk=pk)
    return render(request, 'inventory/budget_detail.html', {'budget': budget})


def export_budgets(request):
    """导出分包预算列表"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    headers = ['编号', '项目名称', '预算总额', '实际产值', '完成进度(%)']
    wb, ws, _ = create_excel_workbook('分包预算列表', headers)
    
    budgets = Budget.objects.all()
    row = 2
    for b in budgets:
        ws.cell(row=row, column=1, value=b.code)
        ws.cell(row=row, column=2, value=b.project.name if b.project else '')
        ws.cell(row=row, column=3, value=float(b.get_budget_total()))
        ws.cell(row=row, column=4, value=float(b.get_actual_value()))
        ws.cell(row=row, column=5, value=float(b.get_completion_progress()))
        row += 1
    
    set_column_widths(ws, [12, 25, 15, 15, 12])
    filename = f'分包预算列表_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return make_excel_response(wb, filename)


def export_budget_detail(request, pk):
    """导出分包预算详情"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    budget = get_object_or_404(Budget, pk=pk)
    
    headers = ['清单序号', '清单名称', '分类', '施工参数', '计量单位', '工程量', '单价', '合价']
    wb, ws, _ = create_excel_workbook(f'预算_{budget.code}', headers)
    
    ws.cell(row=2, column=1, value='编号')
    ws.cell(row=2, column=2, value=budget.code)
    ws.cell(row=3, column=1, value='项目名称')
    ws.cell(row=3, column=2, value=budget.project.name if budget.project else '')
    ws.cell(row=4, column=1, value='预算总额')
    ws.cell(row=4, column=2, value=float(budget.get_budget_total()))
    ws.cell(row=5, column=1, value='实际产值')
    ws.cell(row=5, column=2, value=float(budget.get_actual_value()))
    ws.cell(row=6, column=1, value='完成进度')
    ws.cell(row=6, column=2, value=f'{float(budget.get_completion_progress())}%')
    
    row = 8
    for item in budget.budget_items.all():
        ws.cell(row=row, column=1, value=item.item_order)
        ws.cell(row=row, column=2, value=item.subcontract_list.name)
        ws.cell(row=row, column=3, value=item.subcontract_list.category or '')
        ws.cell(row=row, column=4, value=item.subcontract_list.construction_params or '')
        ws.cell(row=row, column=5, value=item.subcontract_list.unit or '')
        ws.cell(row=row, column=6, value=float(item.quantity) if item.quantity else 0)
        ws.cell(row=row, column=7, value=float(item.unit_price) if item.unit_price else 0)
        ws.cell(row=row, column=8, value=float(item.total_amount) if item.total_amount else 0)
        row += 1
    
    set_column_widths(ws, [12, 25, 12, 18, 10, 12, 12, 15])
    filename = f'预算_{budget.code}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return make_excel_response(wb, filename)
