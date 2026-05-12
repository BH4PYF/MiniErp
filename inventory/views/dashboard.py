from datetime import date
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Sum, Count
from django.shortcuts import render, redirect

from ..models import Project, Material, Supplier, InboundRecord, Contract, Measurement, Settlement, Budget, BudgetItem, MaterialPlan, PurchasePlan, Delivery, Subcontractor


@login_required
def dashboard(request):
    is_sub = hasattr(request.user, 'profile') and request.user.profile.is_subcontractor

    if is_sub:
        # ------ 分包商仪表盘 ------
        sub_contracts = Contract.objects.filter(
            subcontractor__user_profiles__user=request.user,
            is_deleted=False,
        ).select_related('project', 'subcontractor')

        contract_data = []
        for c in sub_contracts:
            contract_total = c.get_contract_total()
            measured_cumulative = c.get_actual_value()
            progress = c.get_completion_progress()
            contract_data.append({
                'id': c.id,
                'code': c.code,
                'project_name': c.project.name if c.project else '',
                'contract_total': contract_total,
                'measured_cumulative': measured_cumulative,
                'progress': progress,
            })

        contracts_count = sub_contracts.count()
        measurements_count = Measurement.objects.filter(
            contract__in=sub_contracts, is_deleted=False,
        ).count()
        settlements = Settlement.objects.filter(
            contract__in=sub_contracts, is_deleted=False,
        )
        settlements_count = settlements.count()
        settlements_total = settlements.aggregate(
            total=Sum('final_amount')
        )['total'] or Decimal('0')

        stats = {
            'contracts_count': contracts_count,
            'measurements_count': measurements_count,
            'settlements_count': settlements_count,
            'settlements_total': settlements_total,
        }

        response = render(request, 'inventory/dashboard.html', {
            'is_subcontractor': True,
            'contract_data': contract_data,
            'stats': stats,
        })
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    # ------ 管理员/物资部仪表盘 (原有逻辑) ------
    today = date.today()
    project_progress_id = request.GET.get('project_progress')
    project_material_id = request.GET.get('project_material')
    selected_project_progress = None
    selected_project_material = None
    selected_project_progress_id = project_progress_id
    selected_project_material_id = project_material_id
    
    # 只返回前 50 条记录用于模板展示（避免大数据量）
    projects = Project.objects.filter(status__in=['active', 'planning']).order_by('-status', 'code')[:50]
    
    if project_progress_id:
        try:
            selected_project_progress = Project.objects.get(id=project_progress_id)
        except Project.DoesNotExist:
            selected_project_progress = None
    
    if project_material_id:
        try:
            selected_project_material = Project.objects.get(id=project_material_id)
        except Project.DoesNotExist:
            selected_project_material = None
    
    # 构建缓存键
    cache_key = f'dashboard_stats_{today}_{project_progress_id or "none"}_{project_material_id or "none"}'
    stats = cache.get(cache_key)

    if stats is None:
        # 使用聚合查询代替全表查询（排除已删除记录）
        projects_count = Project.objects.filter(is_deleted=False).count()
        active_projects_count = Project.objects.filter(status='active', is_deleted=False).count()
        materials_count = Material.objects.filter(is_deleted=False).count()
        suppliers_count = Supplier.objects.filter(is_deleted=False).count()
        
        # 分包管理统计（排除已删除记录）
        contracts_count = Contract.objects.filter(is_deleted=False).count()
        measurements_count = Measurement.objects.filter(is_deleted=False).count()
        settlements_count = Settlement.objects.filter(is_deleted=False).count()
        
        # 材料总额计算（优化：使用annotate和聚合查询，排除已删除记录）
        materials_total = InboundRecord.objects.filter(
            is_deleted=False
        ).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        # 结算总额计算（排除已删除记录）
        settlements_total = Settlement.objects.filter(is_deleted=False).aggregate(total=Sum('final_amount'))['total'] or 0
        
        # 项目进度计算
        project_progress = 0
        if selected_project_progress:
            budget_total = selected_project_progress.budgets.filter(is_deleted=False).aggregate(total=Sum('budget_items__total_amount'))['total'] or 0
            measurement_total = Measurement.objects.filter(
                contract__project=selected_project_progress,
                contract__is_deleted=False,
                is_deleted=False,
            ).aggregate(total=Sum('current_value'))['total'] or 0
            if budget_total > 0:
                project_progress = min(100, round((measurement_total / budget_total) * 100, 1))
        else:
            # 优化：使用单次聚合查询计算总预算和总测量值（排除已删除记录）
            # 计算总预算
            total_budget = BudgetItem.objects.filter(
                budget__project__status__in=['active', 'pending'],
                budget__is_deleted=False
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            # 计算总测量值
            total_measurement = Measurement.objects.filter(
                contract__project__status__in=['active', 'pending'],
                contract__is_deleted=False,
                is_deleted=False
            ).aggregate(total=Sum('current_value'))['total'] or 0
            
            if total_budget > 0:
                project_progress = min(100, round((total_measurement / total_budget) * 100, 1))
        
        # 材料节超计算
        material_variance = 0
        material_variance_percentage = 0
        if selected_project_material:
            # 计算入库总额与材料计划的差值
            # 获取项目的所有入库总额（排除已删除记录）
            inbound_total = selected_project_material.inbound_records.filter(is_deleted=False).aggregate(total=Sum('total_amount'))['total'] or 0
            # 获取项目的所有材料计划总额（排除已删除记录）
            material_plan_total = selected_project_material.material_plans.filter(is_deleted=False).aggregate(total=Sum('total_amount'))['total'] or 0
            material_variance = inbound_total - material_plan_total
            if material_plan_total > 0:
                material_variance_percentage = (material_variance / material_plan_total) * 100
        else:
            # 优化：使用单次聚合查询计算总入库和总材料计划（排除已删除记录）
            # 计算总入库（只统计活跃/待定项目，且排除已删除的入库记录）
            total_inbound = InboundRecord.objects.filter(
                project__status__in=['active', 'pending'],
                is_deleted=False
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            # 计算总材料计划（只统计活跃/待定项目，且排除已删除的材料计划）
            total_material_plan = MaterialPlan.objects.filter(
                project__status__in=['active', 'pending'],
                is_deleted=False
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            material_variance = total_inbound - total_material_plan
            if total_material_plan > 0:
                material_variance_percentage = (material_variance / total_material_plan) * 100

        # 获取今日入库统计（合并为一次查询，排除已删除记录）
        today_stats = InboundRecord.objects.filter(date=today, is_deleted=False).aggregate(
            count=Count('id'),
            total=Sum('total_amount'),
        )

        stats = {
            'projects_count': projects_count,
            'active_projects_count': active_projects_count,
            'materials_count': materials_count,
            'suppliers_count': suppliers_count,
            'contracts_count': contracts_count,
            'measurements_count': measurements_count,
            'settlements_count': settlements_count,
            'materials_total': materials_total,
            'settlements_total': settlements_total,
            'project_progress': project_progress,
            'material_variance': material_variance,
            'material_variance_percentage': material_variance_percentage,
            'today_inbound_count': today_stats['count'],
            'today_inbound_amount': today_stats['total'] or 0,
        }
        # 缓存 60 秒，平衡实时性与性能
        cache.set(cache_key, stats, 60)

    # 待处理事项
    pending_plans = PurchasePlan.objects.select_related('project', 'material', 'supplier').filter(
        status=PurchasePlan.STATUS_PENDING,
        is_deleted=False
    ).order_by('-create_time')[:20]

    pending_deliveries = Delivery.objects.select_related('purchase_plan__project', 'purchase_plan__material', 'supplier').filter(
        status=Delivery.STATUS_PENDING,
        is_deleted=False
    ).order_by('-create_time')[:20]

    materials = Material.objects.select_related('category').all().order_by('code')[:100]
    suppliers = Supplier.objects.all().order_by('code')[:50]

    response = render(request, 'inventory/dashboard.html', {
        'pending_plans': pending_plans,
        'pending_deliveries': pending_deliveries,
        'projects': projects,
        'materials': materials,
        'suppliers': suppliers,
        'today': today,
        'stats': stats,
        'selected_project_progress': selected_project_progress,
        'selected_project_progress_id': selected_project_progress_id,
        'selected_project_material': selected_project_material,
        'selected_project_material_id': selected_project_material_id,
    })
    # 禁止浏览器缓存 HTML，确保刷新时总是拿到最新页面
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
