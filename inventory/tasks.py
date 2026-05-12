"""异步任务模块"""
import logging
from decimal import Decimal
from datetime import datetime

from celery import shared_task
from django.utils import timezone

from .models import (
    Material, InboundRecord, PurchasePlan, Delivery, Category, Supplier,
    MaterialPlan, Project, Subcontractor, SubcontractCategory, SubcontractList,
    Budget, BudgetItem, Contract, ContractItem,
    Measurement, MeasurementItem, Settlement, SettlementItem,
)
from .views.utils import create_excel_workbook, set_column_widths

logger = logging.getLogger('inventory')


@shared_task(bind=True, name='inventory.tasks.export_inventory_excel')
def export_inventory_excel(self, user_id):
    """异步导出库存汇总Excel"""
    logger.info(f'开始导出库存汇总Excel，用户ID: {user_id}')
    
    try:
        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id)
        
        headers = ['材料编号', '材料名称', '分类', '规格', '单位', '累计入库量', '安全库存', '入库均价', '入库总值']
        wb, ws, _ = create_excel_workbook('入库汇总', headers, style='report')
        
        # 限制查询数量
        MAX_EXPORT_ROWS = 10000
        materials_qs = Material.objects.select_related('category').all()[:MAX_EXPORT_ROWS]
        
        # 批量聚合入库数据
        from django.db.models import Sum
        inbound_agg = InboundRecord.objects.filter(
            material_id__in=materials_qs.values_list('pk', flat=True)
        ).values('material_id').annotate(
            total_qty=Sum('quantity'),
            total_amount=Sum('total_amount'),
        )
        
        agg_map = {
            row['material_id']: {
                'total_qty': row['total_qty'] or Decimal('0'),
                'total_amount': row['total_amount'] or Decimal('0'),
            }
            for row in inbound_agg
        }
        
        row = 2
        for m in materials_qs.iterator(chunk_size=500):
            agg = agg_map.get(m.pk, {'total_qty': Decimal('0'), 'total_amount': Decimal('0')})
            inbound_qty = agg['total_qty']
            inbound_amount = agg['total_amount']
            avg_cost = (inbound_amount / inbound_qty) if inbound_qty > 0 else Decimal('0')
            inbound_value = inbound_amount if inbound_qty > 0 else Decimal('0')
            
            ws.cell(row=row, column=1, value=m.code)
            ws.cell(row=row, column=2, value=m.name)
            ws.cell(row=row, column=3, value=m.category.name)
            ws.cell(row=row, column=4, value=m.spec)
            ws.cell(row=row, column=5, value=m.unit)
            ws.cell(row=row, column=6, value=float(inbound_qty))
            ws.cell(row=row, column=7, value=float(m.safety_stock))
            ws.cell(row=row, column=8, value=float(avg_cost))
            ws.cell(row=row, column=9, value=float(inbound_value))
            row += 1
        
        set_column_widths(ws, [12, 20, 12, 15, 8, 12, 10, 10, 12])
        
        # 保存文件到临时位置
        import os
        from django.conf import settings
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(temp_dir, exist_ok=True)
        
        filename = f'inventory_summary_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        file_path = os.path.join(temp_dir, filename)
        wb.save(file_path)
        
        logger.info(f'库存汇总Excel导出完成，文件路径: {file_path}')
        return {
            'success': True,
            'filename': filename,
            'file_path': file_path,
            'download_url': f'/media/exports/{filename}'
        }
        
    except Exception as e:
        logger.error(f'导出库存汇总Excel失败: {str(e)}', exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(bind=True, name='inventory.tasks.export_inbound_excel')
def export_inbound_excel(self, user_id, date_from=None, date_to=None, project_id=None, material_id=None, supplier_id=None):
    """异步导出入库记录Excel"""
    logger.info(f'开始导出入库记录Excel，用户ID: {user_id}')
    
    try:
        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id)
        
        headers = ['入库单号', '日期', '项目', '材料', '单位', '规格', '数量', '单价', '总金额', '供应商']
        wb, ws, _ = create_excel_workbook('入库记录', headers, style='primary')
        
        # 查询入库记录
        records = InboundRecord.objects.select_related('project', 'material', 'supplier')
        
        if date_from:
            records = records.filter(date__gte=date_from)
        if date_to:
            records = records.filter(date__lte=date_to)
        if project_id:
            records = records.filter(project_id=project_id)
        if material_id:
            records = records.filter(material_id=material_id)
        if supplier_id:
            records = records.filter(supplier_id=supplier_id)
        
        MAX_EXPORT_ROWS = 10000
        records = records[:MAX_EXPORT_ROWS]
        
        row = 2
        for r in records:
            ws.cell(row=row, column=1, value=r.no)
            ws.cell(row=row, column=2, value=str(r.date))
            ws.cell(row=row, column=3, value=r.project.name)
            ws.cell(row=row, column=4, value=r.material.name)
            ws.cell(row=row, column=5, value=r.material.unit)
            ws.cell(row=row, column=6, value=r.spec or r.material.spec)
            ws.cell(row=row, column=7, value=float(r.quantity))
            ws.cell(row=row, column=8, value=float(r.unit_price))
            ws.cell(row=row, column=9, value=float(r.total_amount))
            ws.cell(row=row, column=10, value=r.supplier.name)
            row += 1
        
        set_column_widths(ws, [12, 12, 20, 20, 8, 15, 10, 10, 12, 20])
        
        # 保存文件
        import os
        from django.conf import settings
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(temp_dir, exist_ok=True)
        
        filename = f'inbound_records_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        file_path = os.path.join(temp_dir, filename)
        wb.save(file_path)
        
        logger.info(f'入库记录Excel导出完成，文件路径: {file_path}')
        return {
            'success': True,
            'filename': filename,
            'file_path': file_path,
            'download_url': f'/media/exports/{filename}'
        }
        
    except Exception as e:
        logger.error(f'导出入库记录Excel失败: {str(e)}', exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(bind=True, name='inventory.tasks.export_purchase_plans')
def export_purchase_plans(self, user_id, status=None, project_id=None, search_query=None):
    """异步导出采购计划Excel"""
    logger.info(f'开始导出采购计划Excel，用户ID: {user_id}')
    
    try:
        from django.contrib.auth.models import User
        from django.db.models import Q
        user = User.objects.get(id=user_id)
        
        headers = [
            '计划编号', '项目', '材料', '规格', '单位',
            '数量', '供应商', '预计金额', '计划日期', '状态'
        ]
        wb, ws, _ = create_excel_workbook('采购计划列表', headers, style='primary')
        
        # 查询采购计划
        plans = PurchasePlan.objects.select_related(
            'project', 'material', 'supplier'
        ).all().order_by('-planned_date', '-create_time')
        
        if status:
            plans = plans.filter(status=status)
        if project_id:
            plans = plans.filter(project_id=project_id)
        if search_query:
            plans = plans.filter(Q(no__icontains=search_query) | Q(material__name__icontains=search_query))
        
        MAX_EXPORT_ROWS = 10000
        plans = plans[:MAX_EXPORT_ROWS]
        
        row = 2
        for p in plans:
            status_display = dict(PurchasePlan.STATUS_CHOICES).get(p.status, p.status)
            
            ws.cell(row=row, column=1, value=p.no)
            ws.cell(row=row, column=2, value=f"{p.project.code} - {p.project.name}")
            ws.cell(row=row, column=3, value=p.material.name)
            ws.cell(row=row, column=4, value=p.spec or '-')
            ws.cell(row=row, column=5, value=p.material.unit)
            ws.cell(row=row, column=6, value=float(p.quantity))
            ws.cell(row=row, column=7, value=p.supplier.name if p.supplier else '-')
            ws.cell(row=row, column=8, value=float(p.total_amount))
            ws.cell(row=row, column=9, value=str(p.planned_date) if p.planned_date else '-')
            ws.cell(row=row, column=10, value=status_display)
            row += 1
        
        set_column_widths(ws, [15, 25, 20, 15, 8, 10, 15, 12, 12, 10])
        
        # 保存文件
        import os
        from django.conf import settings
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(temp_dir, exist_ok=True)
        
        filename = f'purchase_plans_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        file_path = os.path.join(temp_dir, filename)
        wb.save(file_path)
        
        logger.info(f'采购计划Excel导出完成，文件路径: {file_path}')
        return {
            'success': True,
            'filename': filename,
            'file_path': file_path,
            'download_url': f'/media/exports/{filename}'
        }
        
    except Exception as e:
        logger.error(f'导出采购计划Excel失败: {str(e)}', exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(bind=True, name='inventory.tasks.export_deliveries')
def export_deliveries(self, user_id, supplier_id=None):
    """异步导出发货单Excel"""
    logger.info(f'开始导出发货单Excel，用户ID: {user_id}')
    
    try:
        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id)
        
        headers = [
            '发货单号', '采购计划号', '项目', '材料', '规格型号',
            '单位', '数量', '单价', '总金额', '供应商', '送货方式',
            '车牌号/运单号', '状态', '发货时间', '创建时间'
        ]
        wb, ws, _ = create_excel_workbook('发货单列表', headers, style='primary')
        
        # 查询发货单
        deliveries = Delivery.objects.select_related(
            'purchase_plan', 'purchase_plan__project', 'purchase_plan__material', 'supplier'
        ).all().order_by('-create_time')
        
        if supplier_id:
            deliveries = deliveries.filter(supplier_id=supplier_id)
        
        MAX_EXPORT_ROWS = 10000
        deliveries = deliveries[:MAX_EXPORT_ROWS]
        
        row = 2
        for d in deliveries:
            supplier_name = d.supplier.name if d.supplier else '-'
            
            if d.shipping_method == 'special':
                shipping_display = '专车'
                shipping_detail = d.plate_number or '-'
            else:
                shipping_display = '物流'
                shipping_detail = d.tracking_no or '-'
            
            ws.cell(row=row, column=1, value=d.no)
            ws.cell(row=row, column=2, value=d.purchase_plan.no)
            ws.cell(row=row, column=3, value=d.purchase_plan.project.name)
            ws.cell(row=row, column=4, value=d.purchase_plan.material.name)
            ws.cell(row=row, column=5, value=d.purchase_plan.material.spec or d.purchase_plan.spec or '-')
            ws.cell(row=row, column=6, value=d.purchase_plan.material.unit)
            ws.cell(row=row, column=7, value=float(d.actual_quantity))
            ws.cell(row=row, column=8, value=float(d.actual_unit_price))
            ws.cell(row=row, column=9, value=float(d.actual_total_amount))
            ws.cell(row=row, column=10, value=supplier_name)
            ws.cell(row=row, column=11, value=shipping_display)
            ws.cell(row=row, column=12, value=shipping_detail)
            ws.cell(row=row, column=13, value=dict(Delivery.STATUS_CHOICES).get(d.status, d.status))
            ws.cell(row=row, column=14, value=str(d.ship_time) if d.ship_time else '-')
            ws.cell(row=row, column=15, value=str(d.create_time))
            row += 1
        
        set_column_widths(ws, [12, 15, 20, 20, 15, 8, 10, 10, 12, 15, 15, 15, 10, 15, 15])
        
        # 保存文件
        import os
        from django.conf import settings
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(temp_dir, exist_ok=True)
        
        filename = f'deliveries_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        file_path = os.path.join(temp_dir, filename)
        wb.save(file_path)
        
        logger.info(f'发货单Excel导出完成，文件路径: {file_path}')
        return {
            'success': True,
            'filename': filename,
            'file_path': file_path,
            'download_url': f'/media/exports/{filename}'
        }
        
    except Exception as e:
        logger.error(f'导出发货单Excel失败: {str(e)}', exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(bind=True, name='inventory.tasks.export_material_plans')
def export_material_plans(self, user_id, project_id=None, search_query=None, start_date=None, end_date=None):
    """异步导出材料计划Excel"""
    logger.info(f'开始导出材料计划Excel，用户ID: {user_id}')
    
    try:
        from django.contrib.auth.models import User
        from django.db.models import Q
        user = User.objects.get(id=user_id)
        
        headers = [
            '计划编号', '项目', '计划日期', '计划总金额', '创建人', '创建时间'
        ]
        wb, ws, _ = create_excel_workbook('材料计划列表', headers, style='primary')
        
        # 查询材料计划
        plans = MaterialPlan.objects.select_related(
            'project', 'created_by'
        ).filter(is_deleted=False).order_by('-created_at')
        
        if search_query:
            plans = plans.filter(Q(plan_number__icontains=search_query) | Q(project__name__icontains=search_query))
        if project_id:
            plans = plans.filter(project_id=project_id)
        if start_date:
            plans = plans.filter(plan_date__gte=start_date)
        if end_date:
            plans = plans.filter(plan_date__lte=end_date)
        
        MAX_EXPORT_ROWS = 10000
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
        
        set_column_widths(ws, [15, 25, 12, 12, 12, 15])
        
        # 保存文件
        import os
        from django.conf import settings
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(temp_dir, exist_ok=True)
        
        filename = f'material_plans_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        file_path = os.path.join(temp_dir, filename)
        wb.save(file_path)
        
        logger.info(f'材料计划Excel导出完成，文件路径: {file_path}')
        return {
            'success': True,
            'filename': filename,
            'file_path': file_path,
            'download_url': f'/media/exports/{filename}'
        }
        
    except Exception as e:
        logger.error(f'导出材料计划Excel失败: {str(e)}', exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(bind=True, name='inventory.tasks.backup_data')
def backup_data_task(self, user_id):
    """异步备份系统数据"""
    logger.info(f'开始备份系统数据，用户ID: {user_id}')
    
    try:
        from django.contrib.auth.models import User
        import json
        from django.http import HttpResponse
        from django.utils.http import make_attachment_disposition
        from django.db.models import Model
        from decimal import Decimal
        
        user = User.objects.get(id=user_id)
        
        MAX_BACKUP_ROWS = 50000
        
        def decimal_default(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            return obj
        
        data = {
            'timestamp': timezone.now().isoformat(),
            'projects': list(Project.all_objects.values()[:MAX_BACKUP_ROWS]),
            'categories': list(Category.all_objects.values()[:MAX_BACKUP_ROWS]),
            'materials': list(Material.objects.values()[:MAX_BACKUP_ROWS]),
            'suppliers': list(Supplier.all_objects.values()[:MAX_BACKUP_ROWS]),
            'inbound_records': list(InboundRecord.all_objects.values()[:MAX_BACKUP_ROWS]),
            'purchase_plans': list(PurchasePlan.all_objects.values()[:MAX_BACKUP_ROWS]),
            'deliveries': list(Delivery.all_objects.values()[:MAX_BACKUP_ROWS]),
            'subcontractors': list(Subcontractor.all_objects.values()[:MAX_BACKUP_ROWS]),
            'subcontract_categories': list(SubcontractCategory.all_objects.values()[:MAX_BACKUP_ROWS]),
            'subcontract_lists': list(SubcontractList.all_objects.values()[:MAX_BACKUP_ROWS]),
            'budgets': list(Budget.all_objects.values()[:MAX_BACKUP_ROWS]),
            'budget_items': list(BudgetItem.objects.values()[:MAX_BACKUP_ROWS]),
            'contracts': list(Contract.all_objects.values()[:MAX_BACKUP_ROWS]),
            'contract_items': list(ContractItem.objects.values()[:MAX_BACKUP_ROWS]),
            'measurements': list(Measurement.all_objects.values()[:MAX_BACKUP_ROWS]),
            'measurement_items': list(MeasurementItem.objects.values()[:MAX_BACKUP_ROWS]),
            'settlements': list(Settlement.all_objects.values()[:MAX_BACKUP_ROWS]),
            'settlement_items': list(SettlementItem.objects.values()[:MAX_BACKUP_ROWS]),
            'material_plans': list(MaterialPlan.objects.values()[:MAX_BACKUP_ROWS]),
            'users': list(User.objects.values('id', 'username', 'first_name', 'last_name', 'email', 'is_active', 'is_superuser')[:MAX_BACKUP_ROWS]),
        }
        
        # 保存文件
        import os
        from django.conf import settings
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'backups')
        os.makedirs(temp_dir, exist_ok=True)
        
        filename = f'backup_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=decimal_default, ensure_ascii=False, indent=2)
        
        logger.info(f'系统数据备份完成，文件路径: {file_path}')
        return {
            'success': True,
            'filename': filename,
            'file_path': file_path,
            'download_url': f'/media/backups/{filename}'
        }
        
    except Exception as e:
        logger.error(f'系统数据备份失败: {str(e)}', exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }
