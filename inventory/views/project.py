from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from django.core.paginator import Paginator

from ..models import Project, InboundRecord
from ..services import ProjectService
from .utils import admin_required, log_operation, parse_positive_decimal, combined_permission_required


@combined_permission_required(perm='inventory.view_project', roles=['admin', 'management'])
def project_list(request):
    q = request.GET.get('q', '')
    status_filter = request.GET.get('status', None)
    selected_project = request.GET.get('project', None)
    
    # 使用服务层获取项目列表和统计信息
    projects_with_stats = ProjectService.get_projects_with_statistics(
        search_query=q,
        status_filter=status_filter
    )
    
    # 项目筛选
    if selected_project:
        projects_with_stats = [p for p in projects_with_stats if str(p.id) == selected_project]
    
    # 分页处理
    paginator = Paginator(projects_with_stats, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'inventory/project_list.html', {
        'projects': page_obj, 'q': q, 'status_filter': status_filter,
        'selected_project': selected_project,
        'page_obj': page_obj,
    })


@combined_permission_required(perm='inventory.change_project', roles=['admin', 'management'])
def project_save(request):
    if request.method == 'POST':
        pk = request.POST.get('id')
        name = request.POST.get('name', '').strip()
        
        # 验证必填字段
        if not name:
            return JsonResponse({'error': '项目名称不能为空'}, status=400)
        
        budget, err = parse_positive_decimal(request.POST.get('budget') or '0', '项目预算', allow_zero=True)
        if err:
            return JsonResponse({'error': err}, status=400)
        
        # 准备数据
        data = {
            'name': name,
            'manager': request.POST.get('manager', ''),
            'start_date': request.POST.get('start_date') or None,
            'end_date': request.POST.get('end_date') or None,
            'budget': budget,
            'status': request.POST.get('status', 'active'),
            'remark': request.POST.get('remark', '')
        }
        
        # 使用服务层处理创建或更新
        if pk:
            project, error = ProjectService.update_project(int(pk), data)
            action = 'update'
        else:
            project, error = ProjectService.create_project(data)
            action = 'create'
        
        if error:
            return JsonResponse({'error': error}, status=400)
        
        log_operation(request.user, '项目档案', action, f'{"新增" if action == "create" else "修改"}项目 {project.code} {project.name}', project.code)
        return JsonResponse({'success': True, 'message': '保存成功'})
    return redirect('project_list')


@combined_permission_required(perm='inventory.delete_project', roles=['admin', 'management'])
@require_POST
def project_delete(request, pk):
    success, error = ProjectService.delete_project(int(pk))
    if not success:
        return JsonResponse({'error': error}, status=400)
    
    # 获取项目代码用于日志
    project = Project.objects.get(pk=pk)
    log_operation(request.user, '项目档案', 'delete', f'删除项目 {project.code}', project.code)
    return JsonResponse({'success': True})


@combined_permission_required(perm='inventory.view_project', roles=['admin', 'management'])
@require_GET
def project_detail_api(request, pk):
    obj = get_object_or_404(Project, pk=pk)
    data = {
        'id': obj.pk, 'code': obj.code, 'name': obj.name, 'manager': obj.manager,
        'start_date': str(obj.start_date or ''),
        'end_date': str(obj.end_date or ''), 'budget': str(obj.budget),
        'status': obj.status, 'remark': obj.remark,
    }
    return JsonResponse(data)


@combined_permission_required(perm='inventory.view_project', roles=['admin', 'management'])
@require_GET
def check_project_name(request):
    """检查项目名称是否重复（用于前端实时查重）"""
    name = request.GET.get('name', '').strip()
    exclude_id = request.GET.get('exclude_id')
    
    exists, duplicate_info = ProjectService.check_project_name(
        name, int(exclude_id) if exclude_id else None
    )
    
    if exists and duplicate_info:
        return JsonResponse({
            'exists': True,
            'code': duplicate_info['code'],
            'message': duplicate_info['message']
        })
    else:
        return JsonResponse({'exists': False})
