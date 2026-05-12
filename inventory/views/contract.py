from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from decimal import Decimal
from inventory.models import Contract, ContractItem, Project, Subcontractor, SubcontractList
from inventory.services.rate_limit_service import check_rate_limit
from .utils import create_excel_workbook, set_column_widths, make_excel_response, admin_management_required


def contract_list(request):
    """分包合同列表"""
    if not request.user.is_authenticated:
        return redirect('login')

    if hasattr(request.user, 'profile') and request.user.profile.is_subcontractor:
        contracts = Contract.objects.filter(
            subcontractor__user_profiles__user=request.user,
            is_deleted=False,
        )
    else:
        contracts = Contract.objects.all()

    project_id = request.GET.get('project')
    subcontractor_id = request.GET.get('subcontractor')
    
    if project_id:
        contracts = contracts.filter(project_id=project_id)
    if subcontractor_id:
        contracts = contracts.filter(subcontractor_id=subcontractor_id)
    
    projects = Project.objects.all()
    subcontractors = Subcontractor.objects.all()
    
    context = {
        'contracts': contracts,
        'projects': projects,
        'subcontractors': subcontractors,
        'selected_project': project_id or '',
        'selected_subcontractor': subcontractor_id or '',
    }
    return render(request, 'inventory/contract_list.html', context)


@admin_management_required
def contract_create(request):
    """创建分包合同"""
    projects = Project.objects.all()
    subcontractors = Subcontractor.objects.all()
    
    if request.method == 'POST':
        # 检查速率限制
        if not check_rate_limit(request, 'contract_create', limit=5, window=60):
            messages.error(request, '操作过于频繁，请稍后再试')
            return redirect('contract_list')
        
        try:
            # 生成自动编号 (yyyymmdd000x)
            today = timezone.now().strftime('%Y%m%d')
            # 查找今天的最后一个合同
            last_contract = Contract.objects.filter(code__startswith=today).order_by('-code').first()
            if last_contract:
                # 提取序号并加1
                last_seq = int(last_contract.code[-4:])
                new_seq = last_seq + 1
            else:
                # 如果今天没有合同，查找所有合同的最后一个
                all_last_contract = Contract.objects.order_by('-code').first()
                if all_last_contract:
                    # 检查是否是今天的格式
                    if len(all_last_contract.code) == 12 and all_last_contract.code.isdigit():
                        # 是今天的格式，但不是今天的日期
                        new_seq = 1
                    else:
                        # 是旧格式，从1开始
                        new_seq = 1
                else:
                    # 没有任何合同，从1开始
                    new_seq = 1
            new_code = f'{today}{str(new_seq).zfill(4)}'
            
            with transaction.atomic():
                contract = Contract(
                    code=new_code,
                    name=request.POST.get('name'),
                    project_id=request.POST.get('project'),
                    subcontractor_id=request.POST.get('subcontractor')
                )
                contract.save()
                
                # 处理合同清单
                item_orders = request.POST.getlist('item_order')
                subcontract_list_ids = request.POST.getlist('subcontract_list')
                quantities = request.POST.getlist('quantity')
                unit_prices = request.POST.getlist('unit_price')
                
                for i, item_order in enumerate(item_orders):
                    if item_order and subcontract_list_ids[i] and quantities[i] and unit_prices[i]:
                        ContractItem.objects.create(
                            contract=contract,
                            item_order=item_order,
                            subcontract_list_id=subcontract_list_ids[i],
                            quantity=Decimal(quantities[i]),
                            unit_price=Decimal(unit_prices[i])
                        )
                
            messages.success(request, '分包合同创建成功')
            return redirect('contract_list')
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, f'操作失败，请稍后重试')
    
    subcontract_lists = SubcontractList.objects.all()
    return render(request, 'inventory/contract_create.html', {
        'projects': projects, 
        'subcontractors': subcontractors, 
        'subcontract_lists': subcontract_lists
    })


@admin_management_required
def contract_edit(request, pk):
    """编辑分包合同"""
    contract = get_object_or_404(Contract, pk=pk)
    projects = Project.objects.all()
    subcontractors = Subcontractor.objects.all()
    subcontract_lists = SubcontractList.objects.all()
    
    if request.method == 'POST':
        # 检查速率限制
        if not check_rate_limit(request, 'contract_edit', limit=5, window=60):
            messages.error(request, '操作过于频繁，请稍后再试')
            return redirect('contract_list')
        
        try:
            with transaction.atomic():
                contract.name = request.POST.get('name')
                contract.project_id = request.POST.get('project')
                contract.subcontractor_id = request.POST.get('subcontractor')
                contract.save()
                
                # 删除旧的合同清单
                contract.contract_items.all().delete()
                
                # 处理新的合同清单
                item_orders = request.POST.getlist('item_order')
                subcontract_list_ids = request.POST.getlist('subcontract_list')
                quantities = request.POST.getlist('quantity')
                unit_prices = request.POST.getlist('unit_price')
                
                for i, item_order in enumerate(item_orders):
                    if item_order and subcontract_list_ids[i] and quantities[i] and unit_prices[i]:
                        ContractItem.objects.create(
                            contract=contract,
                            item_order=item_order,
                            subcontract_list_id=subcontract_list_ids[i],
                            quantity=Decimal(quantities[i]),
                            unit_price=Decimal(unit_prices[i])
                        )
                
            messages.success(request, '分包合同更新成功')
            return redirect('contract_list')
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, f'操作失败，请稍后重试')
    
    return render(request, 'inventory/contract_edit.html', {
        'contract': contract, 
        'projects': projects, 
        'subcontractors': subcontractors, 
        'subcontract_lists': subcontract_lists
    })


@admin_management_required
def contract_delete(request, pk):
    """删除分包合同"""
    contract = get_object_or_404(Contract, pk=pk)
    
    if request.method == 'POST':
        try:
            if contract.measurements.exists():
                messages.error(request, f'合同"{contract.name}"已被进度计量引用，不可删除')
            elif contract.settlements.exists():
                messages.error(request, f'合同"{contract.name}"已被分包结算引用，不可删除')
            else:
                contract.delete()
                messages.success(request, '分包合同删除成功')
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, f'操作失败，请稍后重试')
        return redirect('contract_list')
    
    return redirect('contract_list')


def contract_detail(request, pk):
    """分包合同详情"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    contract = get_object_or_404(Contract, pk=pk)
    return render(request, 'inventory/contract_detail.html', {'contract': contract})


def export_contracts(request):
    """导出分包合同列表"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    headers = ['合同编号', '合同名称', '项目名称', '分包商', '合同总额', '实际产值', '完成进度(%)']
    wb, ws, _ = create_excel_workbook('分包合同列表', headers)
    
    contracts = Contract.objects.all()
    row = 2
    for c in contracts:
        ws.cell(row=row, column=1, value=c.code)
        ws.cell(row=row, column=2, value=c.name)
        ws.cell(row=row, column=3, value=c.project.name if c.project else '')
        ws.cell(row=row, column=4, value=c.subcontractor.name if c.subcontractor else '')
        ws.cell(row=row, column=5, value=float(c.get_contract_total()))
        ws.cell(row=row, column=6, value=float(c.get_actual_value()))
        ws.cell(row=row, column=7, value=float(c.get_completion_progress()))
        row += 1
    
    set_column_widths(ws, [15, 25, 20, 20, 15, 15, 12])
    filename = f'分包合同列表_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return make_excel_response(wb, filename)


def export_contract_detail(request, pk):
    """导出分包合同详情"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    contract = get_object_or_404(Contract, pk=pk)
    
    headers = ['清单序号', '清单名称', '分类', '施工参数', '计量单位', '工程量', '单价', '合价']
    wb, ws, _ = create_excel_workbook(f'合同_{contract.code}', headers)
    
    ws.cell(row=2, column=1, value='合同编号')
    ws.cell(row=2, column=2, value=contract.code)
    ws.cell(row=3, column=1, value='合同名称')
    ws.cell(row=3, column=2, value=contract.name)
    ws.cell(row=4, column=1, value='项目名称')
    ws.cell(row=4, column=2, value=contract.project.name if contract.project else '')
    ws.cell(row=5, column=1, value='分包商')
    ws.cell(row=5, column=2, value=contract.subcontractor.name if contract.subcontractor else '')
    ws.cell(row=6, column=1, value='合同总额')
    ws.cell(row=6, column=2, value=float(contract.get_contract_total()))
    ws.cell(row=7, column=1, value='实际产值')
    ws.cell(row=7, column=2, value=float(contract.get_actual_value()))
    
    row = 9
    for item in contract.contract_items.all():
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
    filename = f'合同_{contract.code}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return make_excel_response(wb, filename)
