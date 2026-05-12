from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q, Sum
from django.views.decorators.http import require_GET, require_POST

from django.core.paginator import Paginator

from ..models import Category, Supplier, InboundRecord
from .utils import admin_required, log_operation, save_with_generated_code, create_user_for_supplier, combined_permission_required


@combined_permission_required(perm='inventory.view_supplier', roles=['admin', 'management'])
def supplier_list(request):
    suppliers = Supplier.objects.all()
    q = request.GET.get('q', '')
    main_type = request.GET.get('main_type', '')
    
    # 搜索条件
    if q:
        suppliers = suppliers.filter(Q(code__icontains=q) | Q(name__icontains=q) | Q(contact__icontains=q))
    
    # 主营类型筛选
    if main_type:
        suppliers = suppliers.filter(main_type_id=main_type)

    # 先分页，利用数据库 LIMIT/OFFSET，避免全量加载到内存
    paginator = Paginator(suppliers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 仅对当前页数据做批量聚合，避免 N+1 查询
    page_supplier_ids = [s.pk for s in page_obj]
    purchase_agg = InboundRecord.objects.filter(
        supplier_id__in=page_supplier_ids
    ).values('supplier_id').annotate(
        total_purchase=Sum('total_amount')
    )
    purchase_map = {row['supplier_id']: row['total_purchase'] for row in purchase_agg}

    for s in page_obj:
        s.total_purchase = purchase_map.get(s.pk) or 0

    categories = Category.objects.all().order_by('code')
    return render(request, 'inventory/supplier_list.html', {
        'suppliers': page_obj, 'q': q, 'main_type': main_type, 'categories': categories,
        'page_obj': page_obj,
    })


@combined_permission_required(perm='inventory.change_supplier', roles=['admin', 'management'])
def supplier_save(request):
    if request.method == 'POST':
        pk = request.POST.get('id')
        if pk:
            obj = get_object_or_404(Supplier, pk=pk)
            action = 'update'
        else:
            obj = Supplier()
            action = 'create'
        obj.name = request.POST.get('name', '').strip()
        if not obj.name:
            return JsonResponse({'error': '供应商名称不能为空'}, status=400)
        obj.contact = request.POST.get('contact', '')
        obj.phone = request.POST.get('phone', '')
        obj.address = request.POST.get('address', '')
        main_type_id = request.POST.get('main_type', '')
        if main_type_id:
            obj.main_type_id = int(main_type_id) if main_type_id.isdigit() else None
        else:
            obj.main_type_id = None
        obj.credit_rating = request.POST.get('credit_rating', 'good')
        obj.start_date = request.POST.get('start_date') or None
        obj.remark = request.POST.get('remark', '')
        
        # 保存对象，如果是新增则生成编号
        if pk:
            obj.save()
            log_operation(request.user, '供应商档案', action, f'修改供应商 {obj.code} {obj.name}', obj.code)
        else:
            if save_with_generated_code(obj, 'SUP', Supplier):
                log_operation(request.user, '供应商档案', action, f'新增供应商 {obj.code} {obj.name}', obj.code)
                # 自动为新供应商创建用户账号
                user, err, pwd = create_user_for_supplier(obj)
                if user:
                    log_operation(request.user, '用户管理', 'create',
                                  f'自动创建供应商用户 {user.username}（关联 {obj.code}）', obj.code)
                    return JsonResponse({'success': True, 'message': f'保存成功，已自动创建用户 {user.username}（密码 {pwd}）'})
            else:
                return JsonResponse({'error': '系统繁忙，请稍后重试'}, status=500)
        return JsonResponse({'success': True, 'message': '保存成功'})
    return redirect('supplier_list')


@combined_permission_required(perm='inventory.delete_supplier', roles=['admin', 'management'])
@require_POST
def supplier_delete(request, pk):
    obj = get_object_or_404(Supplier, pk=pk)
    if InboundRecord.all_objects.filter(supplier=obj).exists():
        return JsonResponse({'error': '该供应商已有入库记录，无法删除'}, status=400)
    code = obj.code
    obj.delete()
    log_operation(request.user, '供应商档案', 'delete', f'删除供应商 {code}', code)
    return JsonResponse({'success': True})


@combined_permission_required(perm='inventory.view_supplier', roles=['admin', 'management'])
@require_GET
def supplier_detail_api(request, pk):
    obj = get_object_or_404(Supplier, pk=pk)
    data = {
        'id': obj.pk, 'code': obj.code, 'name': obj.name, 'contact': obj.contact,
        'phone': obj.phone, 'address': obj.address, 'main_type': obj.main_type.id if obj.main_type else '',
        'credit_rating': obj.credit_rating, 'start_date': str(obj.start_date or ''), 'remark': obj.remark,
    }
    return JsonResponse(data)


@combined_permission_required(perm='inventory.view_supplier', roles=['admin', 'management'])
@require_GET
def check_supplier_duplicate(request):
    """检查供应商是否重复（用于前端实时查重）"""
    name = request.GET.get('name', '').strip()
    
    if not name:
        return JsonResponse({'exists': False})
    
    # 查询是否存在相同的供应商名称
    duplicate = Supplier.objects.filter(name=name).first()
    
    if duplicate:
        return JsonResponse({
            'exists': True,
            'code': duplicate.code,
            'message': f'{duplicate.name}（联系人：{duplicate.contact or "无"}, '
                      f'电话：{duplicate.phone or "无"}, '
                      f'编号：{duplicate.code}）'
        })
    else:
        return JsonResponse({'exists': False})
