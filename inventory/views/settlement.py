from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import DatabaseError, IntegrityError, transaction, models
from django.utils import timezone
from decimal import Decimal
from inventory.models import Settlement, SettlementItem, Contract, Project, Subcontractor, SubcontractList, Measurement
from inventory.services.rate_limit_service import check_rate_limit
from inventory.services.dingtalk import DingTalkService
from .utils import create_excel_workbook, set_column_widths, make_excel_response, admin_management_required


def settlement_list(request):
    """分包结算列表"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    project_id = request.GET.get('project')
    subcontractor_id = request.GET.get('subcontractor')
    
    if request.user.profile.is_subcontractor:
        subcontractor_contracts = Contract.objects.filter(subcontractor__user_profiles__user=request.user)
        settlements = Settlement.objects.filter(contract__in=subcontractor_contracts).select_related('contract', 'project', 'subcontractor')
    else:
        settlements = Settlement.objects.select_related('contract', 'project', 'subcontractor').all()
    
    if project_id:
        settlements = settlements.filter(project_id=project_id)
    if subcontractor_id:
        settlements = settlements.filter(subcontractor_id=subcontractor_id)
    
    projects = Project.objects.all()
    subcontractors = Subcontractor.objects.all()
    
    context = {
        'settlements': settlements,
        'projects': projects,
        'subcontractors': subcontractors,
        'selected_project': project_id or '',
        'selected_subcontractor': subcontractor_id or '',
    }
    return render(request, 'inventory/settlement_list.html', context)


@admin_management_required
def settlement_create(request):
    """创建分包结算"""
    contracts = Contract.objects.all()
    
    if request.method == 'POST':
        # 检查速率限制
        if not check_rate_limit(request, 'settlement_create', limit=5, window=60):
            messages.error(request, '操作过于频繁，请稍后再试')
            return redirect('settlement_list')
        
        try:
            today = timezone.now().strftime('%Y%m%d')
            last_settlement = Settlement.all_objects.filter(code__startswith=today).order_by('-code').first()
            if last_settlement:
                last_seq = int(last_settlement.code[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            new_code = f'{today}{str(new_seq).zfill(4)}'
            
            contract = get_object_or_404(Contract, pk=request.POST.get('contract'))
            
            # 计算计量产值 - 汇总所有进度计量的本期产值
            all_measurements = Measurement.objects.filter(contract=contract)
            measurement_value = all_measurements.aggregate(
                total=models.Sum('current_value')
            )['total'] or Decimal('0')
            
            # 获取第一次进度计量的开始日期和最后一次进度计量的截止日期
            first_measurement = all_measurements.order_by('period_start').first()
            last_measurement = all_measurements.order_by('-created_at').first()
            if first_measurement and last_measurement:
                # 如果有进度计量，使用第一次的开始日期和最后一次的截止日期
                request.POST = request.POST.copy()
                request.POST['period_start'] = first_measurement.period_start.strftime('%Y-%m-%d')
                request.POST['period_end'] = last_measurement.period_end.strftime('%Y-%m-%d')
            
            with transaction.atomic():
                deduction_amount = Decimal(request.POST.get('deduction_amount')) if request.POST.get('deduction_amount') else Decimal('0')
                settlement = Settlement(
                    code=new_code,
                    contract=contract,
                    project=contract.project,
                    subcontractor=contract.subcontractor,
                    period_start=request.POST.get('period_start'),
                    period_end=request.POST.get('period_end'),
                    measurement_value=measurement_value,
                    deduction_reason=request.POST.get('deduction_reason'),
                    deduction_amount=deduction_amount
                )
                settlement.save()
                
                # 处理结算清单
                item_orders = request.POST.getlist('item_order')
                subcontract_list_ids = request.POST.getlist('subcontract_list')
                measurement_quantities = request.POST.getlist('measurement_quantity')
                adjusted_quantities = request.POST.getlist('adjusted_quantity')
                unit_prices = request.POST.getlist('unit_price')
                
                for i, item_order in enumerate(item_orders):
                    if item_order and subcontract_list_ids[i] and measurement_quantities[i] and adjusted_quantities[i] and unit_prices[i]:
                        SettlementItem.objects.create(
                            settlement=settlement,
                            item_order=item_order,
                            subcontract_list_id=subcontract_list_ids[i],
                            measurement_quantity=Decimal(measurement_quantities[i]),
                            adjusted_quantity=Decimal(adjusted_quantities[i]),
                            unit_price=Decimal(unit_prices[i])
                        )
                
                settlement.save()

            DingTalkService.notify_if_enabled(
                'settlement_created',
                settlement_no=settlement.code,
                subcontractor_name=str(settlement.subcontractor),
                amount=str(settlement.measurement_value),
                url=f'{request.scheme}://{request.get_host()}/settlements/{settlement.pk}/',
            )

            messages.success(request, '分包结算创建成功')
            return redirect('settlement_list')
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, f'操作失败，请稍后重试')
    
    return render(request, 'inventory/settlement_create.html', {'contracts': contracts})


@admin_management_required
def settlement_edit(request, pk):
    """编辑分包结算"""
    settlement = get_object_or_404(Settlement, pk=pk)
    contracts = Contract.objects.all()
    
    if request.method == 'POST':
        # 检查速率限制
        if not check_rate_limit(request, 'settlement_edit', limit=5, window=60):
            messages.error(request, '操作过于频繁，请稍后再试')
            return redirect('settlement_list')
        
        try:
            contract = get_object_or_404(Contract, pk=request.POST.get('contract'))
            
            # 计算计量产值 - 汇总所有进度计量的本期产值
            all_measurements = Measurement.objects.filter(contract=contract)
            measurement_value = all_measurements.aggregate(
                total=models.Sum('current_value')
            )['total'] or Decimal('0')
            
            # 获取第一次进度计量的开始日期和最后一次进度计量的截止日期
            first_measurement = all_measurements.order_by('period_start').first()
            last_measurement = all_measurements.order_by('-created_at').first()
            if first_measurement and last_measurement:
                # 如果有进度计量，使用第一次的开始日期和最后一次的截止日期
                request.POST = request.POST.copy()
                request.POST['period_start'] = first_measurement.period_start.strftime('%Y-%m-%d')
                request.POST['period_end'] = last_measurement.period_end.strftime('%Y-%m-%d')
            
            with transaction.atomic():
                deduction_amount = Decimal(request.POST.get('deduction_amount')) if request.POST.get('deduction_amount') else Decimal('0')
                settlement.contract = contract
                settlement.project = contract.project
                settlement.subcontractor = contract.subcontractor
                settlement.period_start = request.POST.get('period_start')
                settlement.period_end = request.POST.get('period_end')
                settlement.measurement_value = measurement_value
                settlement.deduction_reason = request.POST.get('deduction_reason')
                settlement.deduction_amount = deduction_amount
                settlement.save()
                
                # 删除旧的结算清单
                settlement.settlement_items.all().delete()
                
                # 处理新的结算清单
                item_orders = request.POST.getlist('item_order')
                subcontract_list_ids = request.POST.getlist('subcontract_list')
                measurement_quantities = request.POST.getlist('measurement_quantity')
                adjusted_quantities = request.POST.getlist('adjusted_quantity')
                unit_prices = request.POST.getlist('unit_price')
                
                for i, item_order in enumerate(item_orders):
                    if item_order and subcontract_list_ids[i] and measurement_quantities[i] and adjusted_quantities[i] and unit_prices[i]:
                        SettlementItem.objects.create(
                            settlement=settlement,
                            item_order=item_order,
                            subcontract_list_id=subcontract_list_ids[i],
                            measurement_quantity=Decimal(measurement_quantities[i]),
                            adjusted_quantity=Decimal(adjusted_quantities[i]),
                            unit_price=Decimal(unit_prices[i])
                        )
                
                settlement.save()
                
            messages.success(request, '分包结算更新成功')
            return redirect('settlement_list')
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, f'操作失败，请稍后重试')
    
    subcontract_lists = SubcontractList.objects.all()
    return render(request, 'inventory/settlement_edit.html', {
        'settlement': settlement, 
        'contracts': contracts, 
        'subcontract_lists': subcontract_lists
    })


@admin_management_required
def settlement_delete(request, pk):
    """删除分包结算"""
    settlement = get_object_or_404(Settlement, pk=pk)
    
    if request.method == 'POST':
        try:
            settlement.delete()
            messages.success(request, '分包结算删除成功')
        except (IntegrityError, DatabaseError) as e:
            messages.error(request, f'操作失败，请稍后重试')
        return redirect('settlement_list')
    
    # 如果是GET请求，直接重定向到列表页面
    return redirect('settlement_list')


def settlement_detail(request, pk):
    """分包结算详情"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    settlement = get_object_or_404(Settlement, pk=pk)
    return render(request, 'inventory/settlement_detail.html', {'settlement': settlement})


def export_settlements(request):
    """导出分包结算列表"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    headers = ['结算编号', '项目名称', '分包商', '合同编号', '计量产值', '扣款金额', '最终结算额']
    wb, ws, _ = create_excel_workbook('分包结算列表', headers)
    
    settlements = Settlement.objects.select_related('contract', 'project', 'subcontractor').all()
    row = 2
    for s in settlements:
        ws.cell(row=row, column=1, value=s.code)
        ws.cell(row=row, column=2, value=s.project.name if s.project else '')
        ws.cell(row=row, column=3, value=s.subcontractor.name if s.subcontractor else '')
        ws.cell(row=row, column=4, value=s.contract.code if s.contract else '')
        ws.cell(row=row, column=5, value=float(s.measurement_value) if s.measurement_value else 0)
        ws.cell(row=row, column=6, value=float(s.deduction_amount) if s.deduction_amount else 0)
        ws.cell(row=row, column=7, value=float(s.final_amount) if s.final_amount else 0)
        row += 1
    
    set_column_widths(ws, [15, 20, 20, 15, 15, 15, 15])
    filename = f'分包结算列表_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return make_excel_response(wb, filename)


def export_settlement_detail(request, pk):
    """导出分包结算详情"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    settlement = get_object_or_404(Settlement, pk=pk)
    
    headers = ['序号', '清单名称', '分类', '施工参数', '计量单位', '计量汇总工程量', '修正后工程量', '单价', '最终产值']
    wb, ws, _ = create_excel_workbook(f'结算_{settlement.code}', headers)
    
    ws.cell(row=2, column=1, value='结算编号')
    ws.cell(row=2, column=2, value=settlement.code)
    ws.cell(row=3, column=1, value='合同名称')
    ws.cell(row=3, column=2, value=settlement.contract.name if settlement.contract else '')
    ws.cell(row=4, column=1, value='项目名称')
    ws.cell(row=4, column=2, value=settlement.project.name if settlement.project else '')
    ws.cell(row=5, column=1, value='分包商')
    ws.cell(row=5, column=2, value=settlement.subcontractor.name if settlement.subcontractor else '')
    ws.cell(row=6, column=1, value='结算周期')
    ws.cell(row=6, column=2, value=f'{settlement.period_start.strftime("%Y-%m-%d")} 至 {settlement.period_end.strftime("%Y-%m-%d")}' if settlement.period_start and settlement.period_end else '')
    ws.cell(row=7, column=1, value='计量产值')
    ws.cell(row=7, column=2, value=float(settlement.measurement_value) if settlement.measurement_value else 0)
    ws.cell(row=8, column=1, value='扣款原因')
    ws.cell(row=8, column=2, value=settlement.deduction_reason or '无')
    ws.cell(row=9, column=1, value='扣款金额')
    ws.cell(row=9, column=2, value=float(settlement.deduction_amount) if settlement.deduction_amount else 0)
    ws.cell(row=10, column=1, value='最终结算额')
    ws.cell(row=10, column=2, value=float(settlement.final_amount) if settlement.final_amount else 0)
    
    row = 12
    for item in settlement.settlement_items.all():
        ws.cell(row=row, column=1, value=item.item_order)
        ws.cell(row=row, column=2, value=item.subcontract_list.name)
        ws.cell(row=row, column=3, value=item.subcontract_list.category or '')
        ws.cell(row=row, column=4, value=item.subcontract_list.construction_params or '')
        ws.cell(row=row, column=5, value=item.subcontract_list.unit or '')
        ws.cell(row=row, column=6, value=float(item.measurement_quantity) if item.measurement_quantity else 0)
        ws.cell(row=row, column=7, value=float(item.adjusted_quantity) if item.adjusted_quantity else 0)
        ws.cell(row=row, column=8, value=float(item.unit_price) if item.unit_price else 0)
        ws.cell(row=row, column=9, value=float(item.final_value) if item.final_value else 0)
        row += 1
    
    set_column_widths(ws, [12, 25, 12, 18, 10, 15, 15, 12, 12])
    filename = f'结算_{settlement.code}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return make_excel_response(wb, filename)


def get_measurements_by_contract(request):
    """根据合同获取进度计量数据（包含清单明细）"""
    from django.http import JsonResponse
    from inventory.models import MeasurementItem
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': '未登录'}, status=401)
    
    contract_id = request.GET.get('contract_id')
    if not contract_id:
        return JsonResponse({'measurements': [], 'items': []})
    
    contract = get_object_or_404(Contract, pk=contract_id)
    
    measurements = Measurement.objects.filter(contract=contract).order_by('-created_at')
    
    measurements_list = []
    for m in measurements:
        measurements_list.append({
            'id': m.id,
            'code': m.code,
            'period_start': m.period_start.strftime('%Y-%m-%d'),
            'period_end': m.period_end.strftime('%Y-%m-%d'),
            'current_value': float(m.current_value),
            'cumulative_value': float(m.cumulative_value)
        })
    
    last_measurement = measurements.first()
    items_list = []
    if last_measurement:
        for item in last_measurement.measurement_items.all():
            total_quantity = MeasurementItem.objects.filter(
                subcontract_list=item.subcontract_list,
                measurement__contract=contract,
                measurement__is_deleted=False
            ).aggregate(total=models.Sum('current_quantity'))['total'] or Decimal('0')
            
            items_list.append({
                'item_order': item.item_order,
                'subcontract_list_id': item.subcontract_list.id,
                'subcontract_list_name': item.subcontract_list.name,
                'category': item.subcontract_list.category,
                'construction_params': item.subcontract_list.construction_params,
                'unit': item.subcontract_list.unit,
                'cumulative_quantity': float(total_quantity),
                'unit_price': float(item.unit_price)
            })
    
    return JsonResponse({
        'measurements': measurements_list,
        'items': items_list
    })


def get_measurement_items(request):
    """获取指定进度计量的清单明细"""
    from django.http import JsonResponse
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': '未登录'}, status=401)
    
    measurement_id = request.GET.get('measurement_id')
    if not measurement_id:
        return JsonResponse({'items': []})
    
    measurement = get_object_or_404(Measurement, pk=measurement_id)
    
    items_list = []
    for item in measurement.measurement_items.all():
        items_list.append({
            'item_order': item.item_order,
            'subcontract_list_id': item.subcontract_list.id,
            'subcontract_list_name': item.subcontract_list.name,
            'category': item.subcontract_list.category,
            'construction_params': item.subcontract_list.construction_params,
            'unit': item.subcontract_list.unit,
            'cumulative_quantity': float(item.cumulative_quantity),
            'unit_price': float(item.unit_price)
        })
    
    return JsonResponse({'items': items_list})
