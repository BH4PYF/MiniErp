from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from inventory.models import SubcontractList, SubcontractCategory
from inventory.services.rate_limit_service import check_rate_limit
from .utils import create_excel_workbook, set_column_widths, make_excel_response


def subcontract_list_list(request):
    """分包清单列表"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    # 获取搜索参数
    q = request.GET.get('q', '')
    
    # 构建查询集
    subcontract_lists = SubcontractList.objects.all()
    
    # 应用搜索
    if q:
        subcontract_lists = subcontract_lists.filter(name__icontains=q)
    
    # 获取所有分包清单分类
    categories = SubcontractCategory.objects.all().order_by('category_code')
    return render(request, 'inventory/subcontract_list_list.html', {'subcontract_lists': subcontract_lists, 'categories': categories, 'q': q})


def subcontract_list_create(request):
    """创建分包清单"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    if request.method == 'POST':
        # 检查速率限制
        if not check_rate_limit(request, 'subcontract_list_create', limit=5, window=60):
            messages.error(request, '操作过于频繁，请稍后再试')
            return redirect('subcontract_list_list')
        
        try:
            # 生成自动编号
            last_list = SubcontractList.objects.order_by('-code').first()
            if last_list:
                last_code = int(last_list.code.split('-')[-1])
                new_code = f'SL-{str(last_code + 1).zfill(4)}'
            else:
                new_code = 'SL-0001'
            
            subcontract_list = SubcontractList(
                code=new_code,
                name=request.POST.get('name'),
                category=request.POST.get('category'),
                construction_params=request.POST.get('construction_params'),
                unit=request.POST.get('unit'),
                reference_price=request.POST.get('reference_price'),
                remark=request.POST.get('remark')
            )
            subcontract_list.save()
            messages.success(request, '分包清单创建成功')
        except Exception as e:
            messages.error(request, f'创建失败: {str(e)}')
        finally:
            return redirect('subcontract_list_list')
    
    # 如果是GET请求，直接重定向到列表页面
    return redirect('subcontract_list_list')


def subcontract_list_edit(request, pk):
    """编辑分包清单"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    subcontract_list = get_object_or_404(SubcontractList, pk=pk)
    
    if request.method == 'POST':
        # 检查速率限制
        if not check_rate_limit(request, 'subcontract_list_edit', limit=5, window=60):
            messages.error(request, '操作过于频繁，请稍后再试')
            return redirect('subcontract_list_list')
        
        try:
            subcontract_list.name = request.POST.get('name')
            subcontract_list.category = request.POST.get('category')
            subcontract_list.construction_params = request.POST.get('construction_params')
            subcontract_list.unit = request.POST.get('unit')
            subcontract_list.reference_price = request.POST.get('reference_price')
            subcontract_list.remark = request.POST.get('remark')
            subcontract_list.save()
            messages.success(request, '分包清单更新成功')
        except Exception as e:
            messages.error(request, f'更新失败: {str(e)}')
        finally:
            return redirect('subcontract_list_list')
    
    # 如果是GET请求，直接重定向到列表页面
    return redirect('subcontract_list_list')


def subcontract_list_delete(request, pk):
    """删除分包清单"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    subcontract_list = get_object_or_404(SubcontractList, pk=pk)
    
    if request.method == 'POST':
        try:
            if subcontract_list.contract_items.exists():
                messages.error(request, f'分包清单"{subcontract_list.name}"已被合同引用，不可删除')
            elif subcontract_list.measurement_items.filter(measurement__is_deleted=False).exists():
                messages.error(request, f'分包清单"{subcontract_list.name}"已被进度计量引用，不可删除')
            else:
                subcontract_list.delete()
                messages.success(request, '分包清单删除成功')
        except Exception as e:
            messages.error(request, f'删除失败: {str(e)}')
        return redirect('subcontract_list_list')
    
    return redirect('subcontract_list_list')


def subcontract_list_detail(request, pk):
    """分包清单详情"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    return redirect('subcontract_list_list')


def export_subcontract_lists(request):
    """导出分包清单列表"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    headers = ['清单编号', '清单名称', '分类', '施工参数', '计量单位', '参考单价', '累计完成量', '平均单价']
    wb, ws, _ = create_excel_workbook('分包清单', headers)
    
    subcontract_lists = SubcontractList.objects.all()
    row = 2
    for sl in subcontract_lists:
        ws.cell(row=row, column=1, value=sl.code)
        ws.cell(row=row, column=2, value=sl.name)
        ws.cell(row=row, column=3, value=sl.category or '')
        ws.cell(row=row, column=4, value=sl.construction_params or '')
        ws.cell(row=row, column=5, value=sl.unit or '')
        ws.cell(row=row, column=6, value=float(sl.reference_price) if sl.reference_price else 0)
        ws.cell(row=row, column=7, value=float(sl.get_total_completed_quantity()))
        ws.cell(row=row, column=8, value=float(sl.get_average_price()))
        row += 1
    
    set_column_widths(ws, [12, 25, 12, 18, 10, 12, 12, 12])
    filename = f'分包清单_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return make_excel_response(wb, filename)
