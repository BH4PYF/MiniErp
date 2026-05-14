"""移动端视图"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from ..models import Project, MaterialPlan, InboundRecord, PurchasePlan, Material, Delivery


@login_required
def mobile_dashboard(request):
    """移动端仪表盘"""
    context = {
        'project_count': Project.objects.filter(is_deleted=False).count(),
        'material_plan_count': MaterialPlan.objects.filter(is_deleted=False).count(),
        'inbound_count': InboundRecord.objects.filter(is_deleted=False).count(),
        'purchase_plan_count': PurchasePlan.objects.filter(is_deleted=False).count(),
    }
    return render(request, 'mobile/dashboard.html', context)


@login_required
def mobile_report(request):
    """移动端报表"""
    projects = Project.objects.filter(is_deleted=False).order_by('code')
    context = {
        'projects': projects,
    }
    return render(request, 'mobile/report.html', context)


@login_required
def mobile_material_list(request):
    """移动端材料列表（支持搜索，分页10条）"""
    q = request.GET.get('q', '').strip()
    materials = Material.objects.filter(is_deleted=False).select_related('category')
    if q:
        materials = materials.filter(
            Q(name__icontains=q) | Q(code__icontains=q) | Q(spec__icontains=q)
        )
    materials = materials.order_by('code')

    paginator = Paginator(materials, 10)
    page = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page': page,
        'q': q,
    }
    return render(request, 'mobile/material_list.html', context)


@login_required
def mobile_inbound_list(request):
    """移动端入库记录（最近20条）"""
    records = InboundRecord.objects.filter(is_deleted=False)\
        .select_related('project', 'material', 'supplier')\
        .order_by('-date', '-operate_time')[:20]
    context = {
        'records': records,
    }
    return render(request, 'mobile/inbound_list.html', context)


@login_required
def mobile_delivery_list(request):
    """移动端发货单（最近20条）"""
    deliveries = Delivery.objects.filter(is_deleted=False)\
        .select_related('purchase_plan__material', 'purchase_plan__project', 'supplier')\
        .order_by('-create_time')[:20]
    context = {
        'deliveries': deliveries,
    }
    return render(request, 'mobile/delivery_list.html', context)
