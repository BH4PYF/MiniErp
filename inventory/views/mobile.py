"""移动端视图"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from ..models import Project, MaterialPlan, InboundRecord, PurchasePlan


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
