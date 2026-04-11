from datetime import date
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Sum, Count
from django.shortcuts import render, redirect

from ..models import Project, Material, Supplier, InboundRecord, Contract, Measurement, Settlement


@login_required
def dashboard(request):
    if hasattr(request.user, 'profile') and request.user.profile.role == 'subcontractor':
        return redirect('measurement_list')
    
    today = date.today()
    project_progress_id = request.GET.get('project_progress')
    project_material_id = request.GET.get('project_material')
    selected_project_progress = None
    selected_project_material = None
    selected_project_progress_id = project_progress_id
    selected_project_material_id = project_material_id
    
    # 只返回前 50 条记录用于模板展示（避免大数据量）
    projects = Project.objects.filter(status__in=['active', 'pending']).order_by('-status', 'code')[:50]
    
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
    cache_key = f'dashboard_stats_{today}_{project_progress_id or "all"}_{project_material_id or "all"}'
    stats = cache.get(cache_key)

    if stats is None:
        # 使用聚合查询代替全表查询
        projects_count = Project.objects.count()
        active_projects_count = Project.objects.filter(status='active').count()
        materials_count = Material.objects.count()
        suppliers_count = Supplier.objects.count()
        
        # 分包管理统计
        contracts_count = Contract.objects.count()
        measurements_count = Measurement.objects.count()
        settlements_count = Settlement.objects.count()
        
        # 材料总额计算
        materials_total = 0
        for material in Material.objects.all():
            total_inbound = material.get_total_inbound()
            if total_inbound > 0:
                materials_total += total_inbound * material.standard_price
        
        # 结算总额计算
        from django.db.models import Sum
        settlements_total = Settlement.objects.aggregate(total=Sum('final_amount'))['total'] or 0
        
        # 项目进度计算
        project_progress = 0
        if selected_project_progress:
            from django.db.models import Sum
            budget_total = selected_project_progress.budgets.aggregate(total=Sum('budget_items__total_amount'))['total'] or 0
            measurement_total = 0
            contracts = selected_project_progress.contracts.all()
            for contract in contracts:
                contract_measurement = contract.measurements.aggregate(
                    total=Sum('current_value')
                )['total'] or 0
                measurement_total += contract_measurement
            if budget_total > 0:
                project_progress = min(100, round((measurement_total / budget_total) * 100, 1))
        else:
            total_budget = 0
            total_measurement = 0
            for project in Project.objects.filter(status__in=['active', 'pending']):
                project_budget = project.budgets.aggregate(total=Sum('budget_items__total_amount'))['total'] or 0
                project_measurement = 0
                contracts = project.contracts.all()
                for contract in contracts:
                    contract_measurement = contract.measurements.aggregate(
                        total=Sum('current_value')
                    )['total'] or 0
                    project_measurement += contract_measurement
                total_budget += project_budget
                total_measurement += project_measurement
            if total_budget > 0:
                project_progress = min(100, round((total_measurement / total_budget) * 100, 1))
        
        # 材料节超计算
        material_variance = 0
        material_variance_percentage = 0
        if selected_project_material:
            # 计算入库总额与材料计划的差值
            # 获取项目的所有入库总额
            inbound_total = selected_project_material.inbound_records.aggregate(total=Sum('total_amount'))['total'] or 0
            # 获取项目的所有材料计划总额
            from .material_plan import MaterialPlan
            material_plan_total = selected_project_material.material_plans.aggregate(total=Sum('total_amount'))['total'] or 0
            material_variance = inbound_total - material_plan_total
            if material_plan_total > 0:
                material_variance_percentage = (material_variance / material_plan_total) * 100
        else:
            # 计算所有项目的材料节超
            total_inbound = 0
            total_material_plan = 0
            for project in Project.objects.filter(status__in=['active', 'pending']):
                project_inbound = project.inbound_records.aggregate(total=Sum('total_amount'))['total'] or 0
                project_material_plan = project.material_plans.aggregate(total=Sum('total_amount'))['total'] or 0
                total_inbound += project_inbound
                total_material_plan += project_material_plan
            material_variance = total_inbound - total_material_plan
            if total_material_plan > 0:
                material_variance_percentage = (material_variance / total_material_plan) * 100

        # 获取今日入库统计（合并为一次查询）
        today_stats = InboundRecord.objects.filter(date=today).aggregate(
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

    # 只查询今日入库记录（限制数量）
    recent_inbounds = InboundRecord.objects.select_related('project', 'material', 'supplier').filter(
        date=today
    ).order_by('-operate_time')[:20]

    materials = Material.objects.select_related('category').all().order_by('code')[:100]
    suppliers = Supplier.objects.all().order_by('code')[:50]

    return render(request, 'inventory/dashboard.html', {
        'recent_inbounds': recent_inbounds,
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
