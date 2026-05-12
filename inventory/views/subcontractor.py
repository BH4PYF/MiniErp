from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from inventory.models import Subcontractor, SubcontractCategory
from inventory.services.rate_limit_service import check_rate_limit
from .utils import create_excel_workbook, set_column_widths, make_excel_response, admin_management_required


def subcontractor_list(request):
    """分包商列表"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    # 获取搜索参数
    q = request.GET.get('q', '')
    main_type = request.GET.get('main_type', '')
    
    # 构建查询集
    subcontractors = Subcontractor.objects.all()
    
    # 应用搜索
    if q:
        subcontractors = subcontractors.filter(name__icontains=q) | subcontractors.filter(contact__icontains=q)
    if main_type:
        subcontractors = subcontractors.filter(main_type=main_type)
    
    # 获取所有分包清单分类
    categories = SubcontractCategory.objects.all().order_by('category_code')
    return render(request, 'inventory/subcontractor_list.html', {'subcontractors': subcontractors, 'categories': categories, 'q': q, 'main_type': main_type})


@admin_management_required
def subcontractor_create(request):
    """创建分包商"""
    if request.method == 'POST':
        # 检查速率限制
        if not check_rate_limit(request, 'subcontractor_create', limit=5, window=60):
            messages.error(request, '操作过于频繁，请稍后再试')
            return redirect('subcontractor_list')
        
        try:
            # 生成自动编号
            last_subcontractor = Subcontractor.objects.order_by('-code').first()
            if last_subcontractor:
                last_code = int(last_subcontractor.code.split('-')[-1])
                new_code = f'SC-{str(last_code + 1).zfill(4)}'
            else:
                new_code = 'SC-0001'
            
            subcontractor = Subcontractor(
                code=new_code,
                name=request.POST.get('name'),
                contact=request.POST.get('contact'),
                phone=request.POST.get('phone'),
                main_type=request.POST.get('main_type'),
                credit_rating=request.POST.get('credit_rating'),
                remark=request.POST.get('remark')
            )
            subcontractor.save()
            messages.success(request, '分包商创建成功')
            return redirect('subcontractor_list')
        except Exception as e:
            messages.error(request, f'创建失败: {str(e)}')
    
    # 获取所有分包清单分类
    categories = SubcontractCategory.objects.all().order_by('category_code')
    return render(request, 'inventory/subcontractor_create.html', {'categories': categories})


@admin_management_required
def subcontractor_edit(request, pk):
    """编辑分包商"""
    subcontractor = get_object_or_404(Subcontractor, pk=pk)
    
    if request.method == 'POST':
        # 检查速率限制
        if not check_rate_limit(request, 'subcontractor_edit', limit=5, window=60):
            messages.error(request, '操作过于频繁，请稍后再试')
            return redirect('subcontractor_list')
        
        try:
            subcontractor.name = request.POST.get('name')
            subcontractor.contact = request.POST.get('contact')
            subcontractor.phone = request.POST.get('phone')
            subcontractor.main_type = request.POST.get('main_type')
            subcontractor.credit_rating = request.POST.get('credit_rating')
            subcontractor.remark = request.POST.get('remark')
            subcontractor.save()
            messages.success(request, '分包商更新成功')
            return redirect('subcontractor_list')
        except Exception as e:
            messages.error(request, f'更新失败: {str(e)}')
    
    # 获取所有分包清单分类
    categories = SubcontractCategory.objects.all().order_by('category_code')
    return render(request, 'inventory/subcontractor_edit.html', {'subcontractor': subcontractor, 'categories': categories})


@admin_management_required
def subcontractor_delete(request, pk):
    """删除分包商"""
    subcontractor = get_object_or_404(Subcontractor, pk=pk)
    
    if request.method == 'POST':
        try:
            if subcontractor.contracts.exists():
                messages.error(request, f'分包商"{subcontractor.name}"已被合同引用，不可删除')
            else:
                subcontractor.delete()
                messages.success(request, '分包商删除成功')
        except Exception as e:
            messages.error(request, f'删除失败: {str(e)}')
        return redirect('subcontractor_list')
    
    return redirect('subcontractor_list')


def subcontractor_detail(request, pk):
    """分包商详情"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    return redirect('subcontractor_list')


def export_subcontractors(request):
    """导出分包商列表"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    headers = ['编号', '分包商名称', '负责人', '电话', '主营类型', '信用等级', '累计产值']
    wb, ws, _ = create_excel_workbook('分包商列表', headers)
    
    subcontractors = Subcontractor.objects.all()
    row = 2
    for s in subcontractors:
        credit_map = {'excellent': '优秀', 'good': '良好', 'average': '一般'}
        ws.cell(row=row, column=1, value=s.code)
        ws.cell(row=row, column=2, value=s.name)
        ws.cell(row=row, column=3, value=s.contact or '')
        ws.cell(row=row, column=4, value=s.phone or '')
        ws.cell(row=row, column=5, value=s.main_type or '')
        ws.cell(row=row, column=6, value=credit_map.get(s.credit_rating, s.credit_rating or ''))
        ws.cell(row=row, column=7, value=float(s.get_total_value()))
        row += 1
    
    set_column_widths(ws, [12, 25, 12, 15, 15, 10, 15])
    filename = f'分包商列表_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return make_excel_response(wb, filename)
