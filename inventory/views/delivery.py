import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction, IntegrityError, DatabaseError
from django.utils import timezone
from ..models import (
    Project, Material, Supplier, InboundRecord,
    PurchasePlan, Delivery,
)
from .utils import (
    delivery_required, inventory_required, supplier_required,
    log_operation, generate_no,
    get_supplier_display_name,
    get_supplier_from_user, is_ajax_request, parse_positive_decimal, parse_date,
    create_excel_workbook, set_column_widths, make_excel_response,
)
from ..services.delivery_service import (
    DeliveryStateError,
    confirm_ship as confirm_ship_service,
    quick_receive as quick_receive_service,
)
from ..services.dingtalk import DingTalkService

logger = logging.getLogger('inventory')


@delivery_required
def delivery_list(request):
    """发货单列表（带分页）"""
    from django.core.paginator import Paginator

    # 使用分页代替硬编码限制
    if request.user.profile.is_supplier:
        supplier_obj = get_supplier_from_user(request.user)
        deliveries_qs = Delivery.objects.select_related(
            'purchase_plan', 'purchase_plan__material', 'purchase_plan__project', 'supplier'
        ).filter(supplier=supplier_obj).order_by('-create_time')
        # 供应商仅看到与自己主营材料类型相关的采购中采购计划
        plan_filter = {'status': PurchasePlan.STATUS_PURCHASING}
        if supplier_obj and supplier_obj.main_type_id:
            plan_filter['material__category_id'] = supplier_obj.main_type_id
        available_plans = PurchasePlan.objects.select_related('project', 'material').filter(
            **plan_filter
        ).order_by('-create_time')
    else:
        deliveries_qs = Delivery.objects.select_related(
            'purchase_plan', 'purchase_plan__material', 'purchase_plan__project', 'supplier'
        ).all().order_by('-create_time')
        # 非供应商用户可以看到所有采购中的采购计划（已发货的已创建过发货单，不再显示）
        available_plans = PurchasePlan.objects.select_related('project', 'material').filter(
            status=PurchasePlan.STATUS_PURCHASING
        ).order_by('-create_time')
    
    # 移除分页，获取所有发货单
    deliveries = deliveries_qs.all()

    return render(request, 'inventory/delivery_list.html', {
        'available_plans': available_plans,
        'deliveries': deliveries,
        'is_paginated': False,
    })


@delivery_required
def export_deliveries(request):
    """批量导出发货单"""
    MAX_EXPORT_ROWS = 10000

    headers = [
        '发货单号', '采购计划号', '项目', '材料', '规格型号',
        '单位', '数量', '单价', '总金额', '供应商', '送货方式',
        '车牌号/运单号', '状态', '发货时间', '创建时间'
    ]
    wb, ws, _ = create_excel_workbook('发货单列表', headers, style='primary')

    if request.user.profile.is_supplier:
        supplier_obj = get_supplier_from_user(request.user)
        deliveries = Delivery.objects.select_related(
            'purchase_plan', 'purchase_plan__project', 'purchase_plan__material', 'supplier'
        ).filter(supplier=supplier_obj).order_by('-create_time')[:MAX_EXPORT_ROWS]
    else:
        deliveries = Delivery.objects.select_related(
            'purchase_plan', 'purchase_plan__project', 'purchase_plan__material', 'supplier'
        ).all().order_by('-create_time')[:MAX_EXPORT_ROWS]

    row = 2
    for d in deliveries:
        supplier_name = get_supplier_display_name(d.supplier)

        shipping_info = ''
        if d.shipping_method == 'special':
            shipping_info = f"专车 - {d.plate_number or '-'}"
        else:
            shipping_info = f"物流 - {d.tracking_no or '-'}"

        ws.cell(row=row, column=1, value=d.no)
        ws.cell(row=row, column=2, value=d.purchase_plan.no)
        ws.cell(row=row, column=3, value=f"{d.purchase_plan.project.code} - {d.purchase_plan.project.name}")
        ws.cell(row=row, column=4, value=d.purchase_plan.material.name)
        ws.cell(row=row, column=5, value=d.purchase_plan.material.spec or '-')
        ws.cell(row=row, column=6, value=d.purchase_plan.material.unit)
        ws.cell(row=row, column=7, value=float(d.actual_quantity))
        ws.cell(row=row, column=8, value=float(d.actual_unit_price))
        ws.cell(row=row, column=9, value=float(d.actual_total_amount))
        ws.cell(row=row, column=10, value=supplier_name)
        ws.cell(row=row, column=11, value=d.get_shipping_method_display())
        ws.cell(row=row, column=12, value=shipping_info)
        ws.cell(row=row, column=13, value=d.get_status_display())
        ws.cell(row=row, column=14, value=d.ship_time.strftime('%Y-%m-%d %H:%M:%S') if d.ship_time else '-')
        ws.cell(row=row, column=15, value=d.create_time.strftime('%Y-%m-%d %H:%M:%S'))
        row += 1
    export_count = row - 2

    set_column_widths(ws, [15, 15, 25, 20, 15, 8, 10, 10, 12, 20, 12, 20, 10, 18, 18])

    filename = f'发货单列表_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

    log_operation(request.user, '发货管理', 'export', f'导出{export_count}条发货单记录')
    return make_excel_response(wb, filename)


@delivery_required
def delivery_create(request):
    """创建发货单"""
    if request.method == 'POST':
        plan_id = request.POST.get('purchase_plan_id')
        plan = get_object_or_404(PurchasePlan, pk=plan_id)

        # 只允许采购中的采购计划发货，防止绕过审批流程
        if plan.status != 'purchasing':
            if is_ajax_request(request):
                return JsonResponse({'error': '该采购计划状态不允许发货（需先审批通过）'}, status=400)
            return redirect('delivery_list')

        delivery = Delivery()
        delivery.purchase_plan = plan
        actual_quantity, err = parse_positive_decimal(request.POST.get('actual_quantity'), '发货数量')
        if err:
            return JsonResponse({'error': err}, status=400)
        delivery.actual_quantity = actual_quantity
        actual_unit_price_str = request.POST.get('actual_unit_price', '').strip()
        if not actual_unit_price_str:
            return JsonResponse({'error': '单价不能为空'}, status=400)
        
        actual_unit_price, err = parse_positive_decimal(actual_unit_price_str, '单价', allow_zero=True)
        if err:
            return JsonResponse({'error': err}, status=400)
        
        delivery.actual_unit_price = actual_unit_price
        VALID_SHIPPING = {c[0] for c in Delivery.SHIPPING_CHOICES}
        shipping_method = request.POST.get('shipping_method', 'special')
        if shipping_method not in VALID_SHIPPING:
            shipping_method = 'special'
        delivery.shipping_method = shipping_method
        delivery.plate_number = request.POST.get('plate_number', '')
        delivery.tracking_no = request.POST.get('tracking_no', '')
        # 获取供应商：供应商用户从个人档案获取，管理员从采购计划获取
        if request.user.profile.is_supplier:
            supplier_profile = getattr(request.user, 'profile', None)
            if supplier_profile and supplier_profile.supplier_info:
                delivery.supplier = supplier_profile.supplier_info
            else:
                return JsonResponse({'error': '用户未关联供应商档案'}, status=400)
        else:
            if plan.supplier:
                delivery.supplier = plan.supplier
            else:
                return JsonResponse({'error': '该采购计划未指定供应商'}, status=400)
        delivery.remark = request.POST.get('remark', '')
        # 检查该采购计划是否已存在未删除的发货单
        existing_delivery = Delivery.objects.filter(purchase_plan=plan).first()
        if existing_delivery:
            return JsonResponse({'error': f'该采购计划已存在发货单：{existing_delivery.no}'}, status=400)
        
        with transaction.atomic():
            # 直接使用采购计划编号作为发货单号
            delivery.no = plan.no
            delivery.save()
            plan.status = PurchasePlan.STATUS_SHIPPED
            plan.save()

        log_operation(request.user, '发货管理', 'create',
                      f'创建发货单 {delivery.no} 采购计划:{plan.no} 数量:{delivery.actual_quantity}', delivery.no)
        DingTalkService.notify_if_enabled(
            'delivery_created',
            delivery_no=delivery.no,
            supplier_name=str(delivery.supplier.name) if delivery.supplier else '未知',
            material_name=str(plan.material.name),
            quantity=str(delivery.actual_quantity),
            url=f'{request.scheme}://{request.get_host()}/deliveries/{delivery.pk}/',
        )
        if is_ajax_request(request):
            return JsonResponse({'success': True, 'message': '发货单创建成功'})
        return redirect('delivery_list')

    purchase_plans = PurchasePlan.objects.select_related('project', 'material').filter(
        status='purchasing'
    )
    return render(request, 'inventory/delivery_create.html', {
        'purchase_plans': purchase_plans,
    })


@delivery_required
def delivery_detail(request, pk):
    """发货单详情"""
    delivery = get_object_or_404(Delivery, pk=pk)

    # 检查权限：供应商用户只能查看自己供应商的发货单
    if request.user.profile.is_supplier:
        supplier_profile = getattr(request.user, 'profile', None)
        if not supplier_profile or not supplier_profile.supplier_info or delivery.supplier != supplier_profile.supplier_info:
            return JsonResponse({'error': '无权限查看此发货单'}, status=403)

    return render(request, 'inventory/delivery_detail.html', {
        'delivery': delivery,
    })


@delivery_required
def delivery_confirm_ship(request, pk):
    """确认发货"""
    delivery = get_object_or_404(Delivery, pk=pk)

    # 检查权限：供应商用户只能操作自己供应商的发货单，管理员可操作所有
    if request.user.profile.is_supplier:
        supplier_profile = getattr(request.user, 'profile', None)
        if not supplier_profile or not supplier_profile.supplier_info or delivery.supplier != supplier_profile.supplier_info:
            return JsonResponse({'error': '无权限操作此发货单'}, status=403)

    if request.method == 'POST':
        is_ajax = is_ajax_request(request)
        if delivery.status != 'pending':
            return JsonResponse({'error': '该发货单当前状态不允许确认发货'}, status=400)

        try:
            confirm_ship_service(delivery)
            log_operation(request.user, '发货管理', 'update', f'确认发货 {delivery.no}', delivery.no)

            if is_ajax:
                return JsonResponse({'success': True, 'message': '确认发货成功'})
            return redirect('delivery_list')
        except DeliveryStateError as e:
            return JsonResponse({'error': str(e)}, status=400)
        
        except (IntegrityError, DatabaseError) as e:
            logger.exception('确认发货数据库操作失败')
            return JsonResponse({'error': '确认发货失败：数据库操作异常，请重试'}, status=500)

    return redirect('delivery_list')


@delivery_required
@require_GET
def delivery_detail_api(request, pk):
    """发货单详情API"""
    obj = get_object_or_404(Delivery, pk=pk)
    data = {
        'id': obj.pk,
        'no': obj.no,
        'purchase_plan_id': obj.purchase_plan_id,
        'actual_quantity': str(obj.actual_quantity),
        'actual_unit_price': str(obj.actual_unit_price),
        'shipping_method': obj.shipping_method,
        'plate_number': obj.plate_number,
        'tracking_no': obj.tracking_no,
        'status': obj.status,
        'remark': obj.remark,
    }
    return JsonResponse(data)


@delivery_required
def delivery_edit(request, pk):
    """编辑发货单"""
    delivery = get_object_or_404(Delivery, pk=pk)
    
    # 检查权限：供应商用户只能编辑自己供应商的发货单
    if request.user.profile.is_supplier:
        supplier_profile = getattr(request.user, 'profile', None)
        if not supplier_profile or not supplier_profile.supplier_info or delivery.supplier != supplier_profile.supplier_info:
            return JsonResponse({'error': '无权限编辑此发货单'}, status=403)
    
    if request.method == 'POST':
        is_ajax = is_ajax_request(request)
        
        # 解析表单数据
        actual_quantity, err = parse_positive_decimal(request.POST.get('actual_quantity'), '发货数量')
        if err:
            return JsonResponse({'error': err}, status=400)
            
        actual_unit_price, err = parse_positive_decimal(request.POST.get('actual_unit_price'), '单价', allow_zero=True)
        if err:
            return JsonResponse({'error': err}, status=400)
            
        VALID_SHIPPING = {c[0] for c in Delivery.SHIPPING_CHOICES}
        shipping_method = request.POST.get('shipping_method', 'special')
        if shipping_method not in VALID_SHIPPING:
            shipping_method = 'special'
            
        plate_number = request.POST.get('plate_number', '')
        tracking_no = request.POST.get('tracking_no', '')
        remark = request.POST.get('remark', '')
        
        try:
            with transaction.atomic():
                delivery.actual_quantity = actual_quantity
                delivery.actual_unit_price = actual_unit_price
                delivery.shipping_method = shipping_method
                delivery.plate_number = plate_number
                delivery.tracking_no = tracking_no
                delivery.remark = remark
                delivery.save()
                
                log_operation(request.user, '发货管理', 'update',
                              f'编辑发货单 {delivery.no} 数量:{delivery.actual_quantity}', delivery.no)
                
                if is_ajax:
                    return JsonResponse({'success': True, 'message': '发货单编辑成功'})
                return redirect('delivery_list')
                
        except (IntegrityError, DatabaseError) as e:
            logger.exception('编辑发货单数据库操作失败')
            return JsonResponse({'error': '编辑发货单失败：数据库操作异常，请重试'}, status=500)
            
    return render(request, 'inventory/delivery_edit.html', {
        'delivery': delivery,
    })


@delivery_required
def delivery_delete(request, pk):
    """删除发货单"""
    delivery = get_object_or_404(Delivery, pk=pk)
    
    # 检查权限：供应商用户只能删除自己供应商的发货单
    if request.user.profile.is_supplier:
        supplier_profile = getattr(request.user, 'profile', None)
        if not supplier_profile or not supplier_profile.supplier_info or delivery.supplier != supplier_profile.supplier_info:
            return JsonResponse({'error': '无权限删除此发货单'}, status=403)
    
    if request.method == 'POST':
        is_ajax = is_ajax_request(request)
        
        try:
            with transaction.atomic():
                # 已入库的发货单直接硬删除，不恢复采购计划状态
                if delivery.status == 'pending':
                    # 待发货状态的发货单删除时，恢复采购计划状态
                    delivery.purchase_plan.status = PurchasePlan.STATUS_PURCHASING
                    delivery.purchase_plan.save()
                
                # 删除发货单 - 使用硬删除
                delivery.hard_delete()
                
                log_operation(request.user, '发货管理', 'delete',
                              f'删除发货单 {delivery.no}', delivery.no)
                
                if is_ajax:
                    return JsonResponse({'success': True, 'message': '发货单删除成功'})
                return redirect('delivery_list')
                
        except (IntegrityError, DatabaseError) as e:
            logger.exception('删除发货单数据库操作失败')
            return JsonResponse({'error': '删除发货单失败：数据库操作异常，请重试'}, status=500)
            
    return redirect('delivery_list')


# ========== 快速收货 ==========

@inventory_required
def quick_receive(request):
    """快速收货页面"""
    deliveries = Delivery.objects.select_related(
        'purchase_plan', 'purchase_plan__project', 'purchase_plan__material', 'supplier'
    ).filter(status='shipped').order_by('-ship_time')[:20]

    return render(request, 'inventory/quick_receive.html', {
        'deliveries': deliveries,
    })


@login_required
@require_GET
def get_delivery_by_no(request):
    """根据发货单号获取发货单信息"""
    delivery_no = request.GET.get('no', '').strip()
    if not delivery_no:
        return JsonResponse({'error': '请输入发货单号'}, status=400)

    try:
        delivery = Delivery.objects.select_related(
            'purchase_plan', 'purchase_plan__project', 'purchase_plan__material', 'supplier'
        ).get(no=delivery_no)

        if delivery.status == Delivery.STATUS_RECEIVED:
            return JsonResponse({'error': '该发货单已收货，无需重复操作'}, status=400)

        if delivery.status != Delivery.STATUS_SHIPPED:
            return JsonResponse({'error': '该发货单尚未发货，无法收货'}, status=400)

        data = {
            'success': True,
            'delivery': {
                'id': delivery.id,
                'no': delivery.no,
                'project_id': delivery.purchase_plan.project_id,
                'project_name': delivery.purchase_plan.project.name,
                'material_id': delivery.purchase_plan.material_id,
                'material_name': delivery.purchase_plan.material.name,
                'material_spec': delivery.purchase_plan.material.spec or '',
                'quantity': str(delivery.actual_quantity),
                'unit_price': str(delivery.actual_unit_price),
                'total_amount': str(delivery.actual_total_amount),
                'supplier_id': delivery.supplier_id,
                'supplier_name': get_supplier_display_name(delivery.supplier),
                'shipping_method': delivery.get_shipping_method_display(),
                'plate_number': delivery.plate_number or '',
                'tracking_no': delivery.tracking_no or '',
                'ship_time': delivery.ship_time.strftime('%Y-%m-%d %H:%M') if delivery.ship_time else '',
            }
        }
        return JsonResponse(data)

    except Delivery.DoesNotExist:
        return JsonResponse({'error': '未找到该发货单，请检查单号是否正确'}, status=404)


@inventory_required
@require_POST
def quick_receive_confirm(request):
    """确认收货并创建入库记录"""
    delivery_id = request.POST.get('delivery_id')
    
    try:
        receive_date_raw = request.POST.get('receive_date', '')
        receive_date = parse_date(receive_date_raw) or timezone.now().date()

        remark = request.POST.get('remark', '')

        inbound, delivery = quick_receive_service(
            delivery_id=delivery_id,
            receive_date=receive_date,
            location='',
            remark=remark,
            operator=request.user,
        )

        log_operation(
            request.user, '快速收货', 'create',
            f'扫码收货 发货单:{delivery.no} -> 入库单:{inbound.no} 材料:{inbound.material.name} 数量:{inbound.quantity}',
            inbound.no
        )

        DingTalkService.notify_if_enabled(
            'inbound_created',
            inbound_no=inbound.no,
            material_name=str(inbound.material.name),
            quantity=str(inbound.quantity),
            project_name=str(inbound.project.name),
            url=f'{request.scheme}://{request.get_host()}/inbound/',
        )

        return JsonResponse({'success': True, 'message': '收货成功', 'inbound_no': inbound.no})
    
    except Delivery.DoesNotExist:
        logger.warning('发货单不存在：%s', delivery_id)
        return JsonResponse({'error': '发货单不存在'}, status=404)
    except DeliveryStateError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except ValueError as e:
        logger.warning('快速收货数据验证失败：%s', e)
        return JsonResponse({'error': f'收货处理失败：{str(e)}'}, status=400)
    except (IntegrityError, DatabaseError) as e:
        logger.exception('快速收货数据库操作失败')
        return JsonResponse({'error': '收货处理失败：数据库操作异常，请重试'}, status=500)
