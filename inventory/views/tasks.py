"""任务管理视图"""
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from celery.result import AsyncResult
from django.utils.timezone import now

from ..tasks import (
    export_inventory_excel, export_inbound_excel,
    export_purchase_plans, export_deliveries, export_material_plans, backup_data_task
)
from .utils import admin_required

logger = logging.getLogger('inventory')


@admin_required
@require_GET
def task_status(request, task_id):
    """查询任务状态"""
    try:
        result = AsyncResult(task_id)
        
        if result.successful():
            data = result.get()
            return JsonResponse({
                'status': 'success',
                'task_id': task_id,
                'result': data
            })
        elif result.failed():
            return JsonResponse({
                'status': 'failed',
                'task_id': task_id,
                'error': str(result.info)
            })
        else:
            return JsonResponse({
                'status': 'pending',
                'task_id': task_id,
                'state': result.state
            })
            
    except Exception as e:
        logger.error(f'查询任务状态失败: {str(e)}', exc_info=True)
        return JsonResponse({
            'status': 'error',
            'task_id': task_id,
            'error': str(e)
        }, status=500)


@admin_required
@require_GET
def export_inventory_async(request):
    """异步导出库存汇总"""
    try:
        task = export_inventory_excel.delay(request.user.id)
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': '导出任务已开始，您可以通过任务ID查询进度'
        })
    except Exception as e:
        logger.error(f'启动库存导出任务失败: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@admin_required
@require_GET
def export_inbound_async(request):
    """异步导出入库记录"""
    try:
        task = export_inbound_excel.delay(
            request.user.id,
            date_from=request.GET.get('date_from'),
            date_to=request.GET.get('date_to'),
            project_id=request.GET.get('project'),
            material_id=request.GET.get('material'),
            supplier_id=request.GET.get('supplier')
        )
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': '导出任务已开始，您可以通过任务ID查询进度'
        })
    except Exception as e:
        logger.error(f'启动入库记录导出任务失败: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@admin_required
@require_GET
def export_purchase_plans_async(request):
    """异步导出采购计划"""
    try:
        task = export_purchase_plans.delay(
            request.user.id,
            status=request.GET.get('status'),
            project_id=request.GET.get('project'),
            search_query=request.GET.get('q')
        )
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': '导出任务已开始，您可以通过任务ID查询进度'
        })
    except Exception as e:
        logger.error(f'启动采购计划导出任务失败: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@admin_required
@require_GET
def export_deliveries_async(request):
    """异步导出发货单"""
    try:
        task = export_deliveries.delay(
            request.user.id,
            supplier_id=request.GET.get('supplier')
        )
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': '导出任务已开始，您可以通过任务ID查询进度'
        })
    except Exception as e:
        logger.error(f'启动发货单导出任务失败: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@admin_required
@require_GET
def export_material_plans_async(request):
    """异步导出材料计划"""
    try:
        task = export_material_plans.delay(
            request.user.id,
            project_id=request.GET.get('project'),
            search_query=request.GET.get('q'),
            start_date=request.GET.get('start_date'),
            end_date=request.GET.get('end_date')
        )
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': '导出任务已开始，您可以通过任务ID查询进度'
        })
    except Exception as e:
        logger.error(f'启动材料计划导出任务失败: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@admin_required
@require_POST
def backup_data_async(request):
    """异步备份系统数据"""
    try:
        task = backup_data_task.delay(request.user.id)
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': '备份任务已开始，您可以通过任务ID查询进度'
        })
    except Exception as e:
        logger.error(f'启动备份任务失败: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
