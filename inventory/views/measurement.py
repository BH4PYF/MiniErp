from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from decimal import Decimal
from inventory.models import Measurement, MeasurementItem, Contract, Project, Subcontractor, SubcontractList
from inventory.services.rate_limit_service import check_rate_limit
from .utils import create_excel_workbook, set_column_widths, make_excel_response, admin_management_required


def measurement_list(request):
    """进度计量列表"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    project_id = request.GET.get('project')
    subcontractor_id = request.GET.get('subcontractor')
    
    if request.user.profile.is_subcontractor:
        subcontractor_contracts = Contract.objects.filter(subcontractor__user_profiles__user=request.user)
        measurements = Measurement.objects.filter(contract__in=subcontractor_contracts).select_related('contract', 'project', 'subcontractor')
    else:
        measurements = Measurement.objects.select_related('contract', 'project', 'subcontractor').all()
    
    if project_id:
        measurements = measurements.filter(project_id=project_id)
    if subcontractor_id:
        measurements = measurements.filter(subcontractor_id=subcontractor_id)
    
    projects = Project.objects.all()
    subcontractors = Subcontractor.objects.all()
    
    context = {
        'measurements': measurements,
        'projects': projects,
        'subcontractors': subcontractors,
        'selected_project': project_id or '',
        'selected_subcontractor': subcontractor_id or '',
    }
    return render(request, 'inventory/measurement_list.html', context)


def clear_dashboard_cache(project_id=None):
    """清除仪表盘缓存"""
    from datetime import date
    today = date.today()
    cache_keys = [f'dashboard_stats_{today}_all']
    if project_id:
        cache_keys.append(f'dashboard_stats_{today}_{project_id}')
    else:
        # 清除所有项目的缓存
        for project in Project.objects.all():
            cache_keys.append(f'dashboard_stats_{today}_{project.id}')
    cache.delete_many(cache_keys)


@admin_management_required
def measurement_create(request):
    """创建进度计量"""
    contracts = Contract.objects.all()
    
    if request.method == 'POST':
        # 检查速率限制
        if not check_rate_limit(request, 'measurement_create', limit=5, window=60):
            messages.error(request, '操作过于频繁，请稍后再试')
            return redirect('measurement_list')
        
        try:
            # 生成自动编号 (yyyymmdd000x)
            today = timezone.now().strftime('%Y%m%d')
            last_measurement = Measurement.all_objects.filter(code__startswith=today).order_by('-code').first()
            if last_measurement:
                last_seq = int(last_measurement.code[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            new_code = f'{today}{str(new_seq).zfill(4)}'
            
            contract = get_object_or_404(Contract, pk=request.POST.get('contract'))
            
            # 计算之前产值
            previous_measurements = Measurement.objects.filter(contract=contract).order_by('-created_at')
            previous_value = previous_measurements.first().cumulative_value if previous_measurements else 0
            
            with transaction.atomic():
                measurement = Measurement(
                    code=new_code,
                    contract=contract,
                    project=contract.project,
                    subcontractor=contract.subcontractor,
                    period_start=request.POST.get('period_start'),
                    period_end=request.POST.get('period_end'),
                    previous_value=previous_value
                )
                measurement.save()
                
                # 处理计量清单
                item_orders = request.POST.getlist('item_order')
                subcontract_list_ids = request.POST.getlist('subcontract_list')
                previous_quantities = request.POST.getlist('previous_quantity')
                current_quantities = request.POST.getlist('current_quantity')
                unit_prices = request.POST.getlist('unit_price')
                
                for i, item_order in enumerate(item_orders):
                    if item_order and subcontract_list_ids[i] and previous_quantities[i] and current_quantities[i] and unit_prices[i]:
                        MeasurementItem.objects.create(
                            measurement=measurement,
                            item_order=item_order,
                            subcontract_list_id=subcontract_list_ids[i],
                            previous_quantity=Decimal(previous_quantities[i]),
                            current_quantity=Decimal(current_quantities[i]),
                            unit_price=Decimal(unit_prices[i])
                        )
                
                # 再次保存计量，计算产值
                measurement.save()
                
            # 清除仪表盘缓存
            clear_dashboard_cache(measurement.project_id)
            
            messages.success(request, '进度计量创建成功')
            return redirect('measurement_list')
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, f'操作失败，请稍后重试')
    
    return render(request, 'inventory/measurement_create.html', {'contracts': contracts})


@admin_management_required
def measurement_edit(request, pk):
    """编辑进度计量"""
    measurement = get_object_or_404(Measurement, pk=pk)
    contracts = Contract.objects.all()
    
    if request.method == 'POST':
        # 检查速率限制
        if not check_rate_limit(request, 'measurement_edit', limit=5, window=60):
            messages.error(request, '操作过于频繁，请稍后再试')
            return redirect('measurement_list')
        
        try:
            contract = get_object_or_404(Contract, pk=request.POST.get('contract'))
            
            # 计算之前产值
            previous_measurements = Measurement.objects.filter(contract=contract).exclude(id=measurement.id).order_by('-created_at')
            previous_value = previous_measurements.first().cumulative_value if previous_measurements else 0
            
            with transaction.atomic():
                measurement.contract = contract
                measurement.project = contract.project
                measurement.subcontractor = contract.subcontractor
                measurement.period_start = request.POST.get('period_start')
                measurement.period_end = request.POST.get('period_end')
                measurement.previous_value = previous_value
                measurement.save()
                
                # 删除旧的计量清单
                measurement.measurement_items.all().delete()
                
                # 处理新的计量清单
                item_orders = request.POST.getlist('item_order')
                subcontract_list_ids = request.POST.getlist('subcontract_list')
                previous_quantities = request.POST.getlist('previous_quantity')
                current_quantities = request.POST.getlist('current_quantity')
                unit_prices = request.POST.getlist('unit_price')
                
                for i, item_order in enumerate(item_orders):
                    if item_order and subcontract_list_ids[i] and previous_quantities[i] and current_quantities[i] and unit_prices[i]:
                        MeasurementItem.objects.create(
                            measurement=measurement,
                            item_order=item_order,
                            subcontract_list_id=subcontract_list_ids[i],
                            previous_quantity=Decimal(previous_quantities[i]),
                            current_quantity=Decimal(current_quantities[i]),
                            unit_price=Decimal(unit_prices[i])
                        )
                
                # 再次保存计量，计算产值
                measurement.save()
                
            # 清除仪表盘缓存
            clear_dashboard_cache(measurement.project_id)
            
            messages.success(request, '进度计量更新成功')
            return redirect('measurement_list')
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, f'操作失败，请稍后重试')
    
    return render(request, 'inventory/measurement_edit.html', {
        'measurement': measurement, 
        'contracts': contracts
    })


@admin_management_required
def measurement_delete(request, pk):
    """删除进度计量"""
    measurement = get_object_or_404(Measurement, pk=pk)
    project_id = measurement.project_id
    
    if request.method == 'POST':
        try:
            if measurement.contract.settlements.exists():
                messages.error(request, f'进度计量"{measurement.code}"所属合同已有分包结算，不可删除')
            else:
                measurement.delete()
                messages.success(request, '进度计量删除成功')
                clear_dashboard_cache(project_id)
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, f'操作失败，请稍后重试')
        return redirect('measurement_list')
    
    return redirect('measurement_list')


def measurement_detail(request, pk):
    """进度计量详情"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    measurement = get_object_or_404(Measurement, pk=pk)
    
    return render(request, 'inventory/measurement_detail.html', {
        'measurement': measurement
    })


def export_measurements(request):
    """导出进度计量列表"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    headers = ['计量编号', '合同名称', '项目名称', '分包商', '计量周期开始', '计量周期截止', '之前产值', '本期产值', '累计产值']
    wb, ws, _ = create_excel_workbook('进度计量列表', headers)
    
    measurements = Measurement.objects.select_related('contract', 'project', 'subcontractor').all()
    row = 2
    for m in measurements:
        ws.cell(row=row, column=1, value=m.code)
        ws.cell(row=row, column=2, value=m.contract.name if m.contract else '')
        ws.cell(row=row, column=3, value=m.project.name if m.project else '')
        ws.cell(row=row, column=4, value=m.subcontractor.name if m.subcontractor else '')
        ws.cell(row=row, column=5, value=m.period_start.strftime('%Y-%m-%d') if m.period_start else '')
        ws.cell(row=row, column=6, value=m.period_end.strftime('%Y-%m-%d') if m.period_end else '')
        ws.cell(row=row, column=7, value=float(m.previous_value) if m.previous_value else 0)
        ws.cell(row=row, column=8, value=float(m.current_value) if m.current_value else 0)
        ws.cell(row=row, column=9, value=float(m.cumulative_value) if m.cumulative_value else 0)
        row += 1
    
    set_column_widths(ws, [15, 20, 20, 20, 12, 12, 12, 12, 12])
    filename = f'进度计量列表_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return make_excel_response(wb, filename)


def export_measurement_detail(request, pk):
    """导出进度计量详情"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    measurement = get_object_or_404(Measurement, pk=pk)
    
    headers = ['序号', '清单名称', '分类', '施工参数', '计量单位', '之前数量', '本期数量', '单价', '本期产值']
    wb, ws, _ = create_excel_workbook(f'计量_{measurement.code}', headers)
    
    ws.cell(row=2, column=1, value='计量编号')
    ws.cell(row=2, column=2, value=measurement.code)
    ws.cell(row=3, column=1, value='合同名称')
    ws.cell(row=3, column=2, value=measurement.contract.name if measurement.contract else '')
    ws.cell(row=4, column=1, value='项目名称')
    ws.cell(row=4, column=2, value=measurement.project.name if measurement.project else '')
    ws.cell(row=5, column=1, value='分包商')
    ws.cell(row=5, column=2, value=measurement.subcontractor.name if measurement.subcontractor else '')
    ws.cell(row=6, column=1, value='计量周期')
    ws.cell(row=6, column=2, value=f'{measurement.period_start.strftime("%Y-%m-%d")} 至 {measurement.period_end.strftime("%Y-%m-%d")}' if measurement.period_start and measurement.period_end else '')
    ws.cell(row=7, column=1, value='之前产值')
    ws.cell(row=7, column=2, value=float(measurement.previous_value) if measurement.previous_value else 0)
    ws.cell(row=8, column=1, value='本期产值')
    ws.cell(row=8, column=2, value=float(measurement.current_value) if measurement.current_value else 0)
    ws.cell(row=9, column=1, value='累计产值')
    ws.cell(row=9, column=2, value=float(measurement.cumulative_value) if measurement.cumulative_value else 0)
    
    row = 11
    for item in measurement.measurement_items.all():
        ws.cell(row=row, column=1, value=item.item_order)
        ws.cell(row=row, column=2, value=item.subcontract_list.name)
        ws.cell(row=row, column=3, value=item.subcontract_list.category or '')
        ws.cell(row=row, column=4, value=item.subcontract_list.construction_params or '')
        ws.cell(row=row, column=5, value=item.subcontract_list.unit or '')
        ws.cell(row=row, column=6, value=float(item.previous_quantity) if item.previous_quantity else 0)
        ws.cell(row=row, column=7, value=float(item.current_quantity) if item.current_quantity else 0)
        ws.cell(row=row, column=8, value=float(item.unit_price) if item.unit_price else 0)
        ws.cell(row=row, column=9, value=float(item.current_value) if item.current_value else 0)
        row += 1
    
    set_column_widths(ws, [12, 25, 12, 18, 10, 12, 12, 12, 12])
    filename = f'计量_{measurement.code}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return make_excel_response(wb, filename)


def get_subcontract_lists_by_contract(request):
    """根据合同获取分包清单"""
    from django.http import JsonResponse
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': '未登录'}, status=401)
    
    contract_id = request.GET.get('contract_id')
    if not contract_id:
        return JsonResponse({'items': []})
    
    contract = get_object_or_404(Contract, pk=contract_id)
    contract_items = contract.contract_items.all()
    
    items = []
    for item in contract_items:
        items.append({
            'id': item.subcontract_list.id,
            'name': item.subcontract_list.name,
            'category': item.subcontract_list.category,
            'construction_params': item.subcontract_list.construction_params,
            'unit': item.subcontract_list.unit,
            'quantity': float(item.quantity) if item.quantity else 0,
            'unit_price': float(item.unit_price) if item.unit_price else 0,
            'total_amount': float(item.total_amount) if item.total_amount else 0
        })
    
    return JsonResponse({'items': items})
