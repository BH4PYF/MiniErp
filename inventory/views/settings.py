import json
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db.models import Count
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction, IntegrityError, DatabaseError
from django.utils import timezone

from ..models import (
    Profile, Project, Category, Material, Supplier,
    InboundRecord, OperationLog, SystemSetting, PurchasePlan,
)
from .utils import (
    admin_required, log_operation,
    generate_code, decimal_default, parse_date,
    make_attachment_disposition,
)

logger = logging.getLogger('inventory')


# ========== 系统设置 ==========

@admin_required
def settings_page(request):
    """系统设置页面 - 基础 Tab 数据在页面加载时渲染，其余 Tab 按需 AJAX 加载"""
    import sys
    import django

    company_name = SystemSetting.get_setting('company_name', '材料管理系统 V1.8')

    # 基础设置 Tab 数据
    login_max_attempts = int(SystemSetting.get_setting('login_max_attempts', '5'))
    login_lockout_seconds = int(SystemSetting.get_setting('login_lockout_seconds', '300'))
    login_lockout_minutes = login_lockout_seconds // 60

    # 高级管理 Tab 中的系统信息（开销极小，保留）
    django_version = django.get_version()
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    # 获取数据库类型
    from django.conf import settings
    db_engine = settings.DATABASES['default']['ENGINE']
    if 'postgresql' in db_engine:
        db_type = 'PostgreSQL'
        db_version = '（生产环境）'
    elif 'mysql' in db_engine:
        db_type = 'MySQL'
        db_version = '（生产环境）'
    elif 'sqlite' in db_engine:
        db_type = 'SQLite'
        db_version = '（开发环境）'
    else:
        db_type = 'Unknown'
        db_version = ''
    
    # 系统版本
    system_version = 'V2.0.0'
    system_build = '20260414'

    return render(request, 'inventory/settings.html', {
        'company_name': company_name,
        'login_max_attempts': login_max_attempts,
        'login_lockout_minutes': login_lockout_minutes,
        'django_version': django_version,
        'python_version': python_version,
        'db_type': db_type,
        'db_version': db_version,
        'system_version': system_version,
        'system_build': system_build,
    })


@admin_required
@require_GET
def settings_users_api(request):
    """AJAX 加载用户与权限 Tab 数据"""
    from django.contrib.auth.models import Group

    users = User.objects.select_related('profile').all().order_by('username')
    # 批量补全缺失的 profile，避免逐条 get_or_create 产生 N+1 查询
    users_without_profile = [u for u in users if not hasattr(u, 'profile')]
    if users_without_profile:
        Profile.objects.bulk_create(
            [Profile(user=u) for u in users_without_profile],
            ignore_conflicts=True,
        )
        # 重新加载以获取新建的 profile
        users = User.objects.select_related('profile').all().order_by('username')

    users_data = []
    for user in users:
        users_data.append({
            'id': user.pk,
            'username': user.username,
            'email': user.email or '',
            'role': user.profile.get_role_display() if hasattr(user, 'profile') else '普通用户',
            'is_active': user.is_active,
        })

    groups = Group.objects.prefetch_related('permissions').all().order_by('name')
    permission_matrix = []
    for group in groups:
        perms = list(group.permissions.values_list('codename', flat=True))
        permission_matrix.append({
            'name': group.name,
            'count': len(perms),
            'permissions': perms,
        })

    return JsonResponse({
        'users': users_data,
        'permission_matrix': permission_matrix,
    })


@admin_required
def settings_logs_api(request):
    """AJAX 加载最近操作日志 Tab 数据"""
    recent_logs = OperationLog.objects.all().order_by('-time')[:10]
    logs_data = []
    for log in recent_logs:
        logs_data.append({
            'time': log.time.strftime('%Y-%m-%d %H:%M:%S'),
            'operator': log.operator,
            'module': log.module,
            'op_type': log.op_type,
            'op_type_display': log.get_op_type_display(),
            'details': log.details[:50] if len(log.details) > 50 else log.details,
            'related_no': log.related_no or '-',
        })
    return JsonResponse({'logs': logs_data})


@admin_required
def add_custom_category(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        remark = request.POST.get('remark', '').strip()
        category_type = request.POST.get('category_type', 'material')  # material 或 subcontract
        if name:
            if category_type == 'material':
                if Category.objects.filter(name=name).exists():
                    return JsonResponse({'error': f'材料分类名称「{name}」已存在'}, status=400)
                try:
                    code = generate_code('CAT', Category)
                    Category.objects.create(code=code, name=name, remark=remark)
                    log_operation(request.user, '材料分类', 'create', f'新增自定义分类 {code} {name}', code)
                    return JsonResponse({'success': True, 'message': '材料分类添加成功'})
                except IntegrityError:
                    return JsonResponse({'error': '分类编码冲突，请重试'}, status=400)
            else:
                from ..models import SubcontractCategory
                if SubcontractCategory.objects.filter(category_name=name).exists():
                    return JsonResponse({'error': f'清单分类名称「{name}」已存在'}, status=400)
                try:
                    # 生成清单分类编号，格式为 BAT0001
                    last_list = SubcontractCategory.objects.filter(category_code__startswith='BAT').order_by('-category_code').first()
                    if last_list:
                        try:
                            last_num = int(last_list.category_code[3:])
                            new_num = last_num + 1
                        except (ValueError, IndexError):
                            new_num = 1
                    else:
                        new_num = 1
                    category_code = f"BAT{new_num:04d}"
                    # 确保编码唯一
                    while SubcontractCategory.objects.filter(category_code=category_code).exists():
                        new_num += 1
                        category_code = f"BAT{new_num:04d}"
                    SubcontractCategory.objects.create(
                        category_code=category_code,
                        category_name=name,
                        remark='用户自定义创建'
                    )
                    log_operation(request.user, '清单分类', 'create', f'新增自定义清单分类 {category_code} {name}', category_code)
                    return JsonResponse({'success': True, 'message': '清单分类添加成功'})
                except IntegrityError:
                    return JsonResponse({'error': '分类编码冲突，请重试'}, status=400)
        else:
            return JsonResponse({'error': '分类名称不能为空'}, status=400)
    return redirect('settings_page')


@admin_required
@require_POST
def delete_category(request, pk):
    obj = get_object_or_404(Category, pk=pk)
    if obj.materials.exists():
        return JsonResponse({'error': '该分类下有材料，无法删除'}, status=400)
    code = obj.code
    name = obj.name
    obj.delete()
    log_operation(request.user, '材料分类', 'delete', f'删除分类 {code} {name}', code)
    return JsonResponse({'success': True})


@admin_required
@require_POST
def delete_subcontract_category(request, pk):
    from ..models import SubcontractCategory
    obj = get_object_or_404(SubcontractCategory, pk=pk)
    # 检查是否有使用该清单分类的记录
    # 这里可以添加检查逻辑，比如检查是否有SubcontractList使用了这个分类
    category_code = obj.category_code
    category_name = obj.category_name
    obj.delete()
    log_operation(request.user, '清单分类', 'delete', f'删除清单分类 {category_code} {category_name}', category_code)
    return JsonResponse({'success': True})


@admin_required
def save_system_settings(request):
    """保存系统设置（导航栏标题）"""
    if request.method == 'POST':
        company_name = request.POST.get('company_name', '').strip()

        if company_name:
            SystemSetting.set_setting('company_name', company_name, '公司/项目名称')

        # 清除上下文处理器的缓存，使新名称立即生效
        from django.core.cache import cache
        cache.delete('global_company_name')

        log_operation(request.user, '系统设置', 'update', f'更新系统设置：导航栏标题={company_name}')

        return JsonResponse({
            'success': True,
            'message': '导航栏标题已保存',
            'company_name': company_name or '材料管理系统 V1.8'
        })

    return JsonResponse({'error': '无效请求'}, status=400)


@admin_required
def save_login_security_settings(request):
    """保存登录安全配置（限流参数）"""
    if request.method == 'POST':
        try:
            login_max_attempts = int(request.POST.get('login_max_attempts', '5'))
            login_lockout_minutes = int(request.POST.get('login_lockout_minutes', '5'))
            
            # 验证范围
            if not (1 <= login_max_attempts <= 10):
                return JsonResponse({'error': '最大登录尝试次数必须在 1-10 之间'}, status=400)
            if not (1 <= login_lockout_minutes <= 60):
                return JsonResponse({'error': '锁定时长必须在 1-60 分钟之间'}, status=400)
            
            login_lockout_seconds = login_lockout_minutes * 60
            
            # 保存到系统设置
            SystemSetting.set_setting('login_max_attempts', str(login_max_attempts), '最大登录尝试次数')
            SystemSetting.set_setting('login_lockout_seconds', str(login_lockout_seconds), '登录锁定时间（秒）')
            
            # 清除缓存，使新设置立即生效
            from django.core.cache import cache
            cache.delete('LOGIN_MAX_ATTEMPTS')
            cache.delete('LOGIN_LOCKOUT_SECONDS')
            
            log_operation(request.user, '系统设置', 'update', 
                         f'更新登录安全配置：最大尝试={login_max_attempts}次，锁定={login_lockout_minutes}分钟')
            
            return JsonResponse({
                'success': True,
                'message': f'登录安全配置已保存：最大尝试 {login_max_attempts} 次，锁定 {login_lockout_minutes} 分钟'
            })
        except ValueError:
            return JsonResponse({'error': '请输入有效的数字'}, status=400)

    return JsonResponse({'error': '无效请求'}, status=400)


# ========== 用户管理 ==========

@admin_required
def user_list(request):
    from django.contrib.auth.models import Group
    from ..models import Subcontractor
    # 使用 prefetch_related 来减少数据库查询，按id排序
    users = User.objects.select_related('profile').prefetch_related('groups').order_by('id')
    # 获取所有Django用户组
    groups = Group.objects.all().order_by('name')
    
    # 只使用默认角色，不包含用户分组
    from ..models import Profile
    
    # 创建角色列表，确保包含所有默认角色（除了管理员）
    role_list = []
    
    # 添加默认角色（排除管理员）
    for role_code, role_name in Profile.ROLE_CHOICES:
        if role_code != 'admin':
            role_list.append({'code': role_code, 'name': role_name})
    
    subcontractors = Subcontractor.objects.all()
    
    return render(request, 'inventory/user_list.html', {
        'users': users, 'role_list': role_list, 'subcontractors': subcontractors
    })


@admin_required
def user_save(request):
    """创建或更新用户"""
    from ..models import Profile
    if request.method == 'POST':
        pk = request.POST.get('id')
        if pk:
            user = get_object_or_404(User, pk=pk)
            action = 'update'
        else:
            user = User()
            action = 'create'
        
        # 获取并验证用户名
        username = request.POST.get('username', '').strip()
        if not username:
            return JsonResponse({'error': '用户名不能为空'})
        
        # 验证用户名唯一性（排除自己）
        existing_user = User.objects.filter(username=username)
        if pk:
            existing_user = existing_user.exclude(pk=pk)
        if existing_user.exists():
            return JsonResponse({'error': f'用户名 "{username}" 已存在，请使用其他用户名'})
        
        user.username = username
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.is_active = request.POST.get('is_active', 'on') == 'on'
        user.is_superuser = request.POST.get('is_superuser', 'off') == 'on'
        
        # 密码处理
        password = request.POST.get('password', '')
        random_pwd = None
        if password:
            if len(password) < 8:
                return JsonResponse({'error': '密码长度至少为 8 位'})
            user.set_password(password)
        elif action == 'create':
            # 新建用户时生成随机密码并提示管理员
            import secrets
            random_pwd = secrets.token_urlsafe(12)
            user.set_password(random_pwd)
        
        try:
            with transaction.atomic():
                user.save()
                if not hasattr(user, 'profile'):
                    Profile.objects.create(user=user)
                
                role = request.POST.get('role', 'clerk')
                # 处理用户组分配
                from django.contrib.auth.models import Group
                
                # 创建角色名称到代码的映射
                role_name_to_code = {role_name: role_code for role_code, role_name in Profile.ROLE_CHOICES}
                # 创建角色代码到名称的映射
                role_code_to_name = {role_code: role_name for role_code, role_name in Profile.ROLE_CHOICES}
                
                if role.startswith('group_'):
                    # 移除所有组
                    user.groups.clear()
                    # 添加到指定组
                    group_id = role.split('_')[1]
                    try:
                        group = Group.objects.get(id=group_id)
                        user.groups.add(group)
                        # 检查用户组名称是否与默认角色名称匹配
                        if group.name in role_name_to_code:
                            # 使用对应的默认角色代码
                            user.profile.role = role_name_to_code[group.name]
                        else:
                            # 对于用户组，设置一个默认角色
                            user.profile.role = 'clerk'
                    except Group.DoesNotExist:
                        pass
                else:
                    # 对于普通角色，移除所有组
                    user.groups.clear()
                    user.profile.role = role
                    
                    # 如果是预定义角色，尝试将用户添加到对应的用户组
                    if role in role_code_to_name:
                        role_name = role_code_to_name[role]
                        try:
                            # 查找名称匹配的用户组
                            group = Group.objects.get(name=role_name)
                            user.groups.add(group)
                        except Group.DoesNotExist:
                            # 如果用户组不存在，不做处理
                            pass
                
                user.profile.phone = request.POST.get('phone', '')
                user.profile.save()
                
                # 处理分包商关联
                from ..models import Subcontractor
                user.profile.subcontractors.clear()
                if role == 'subcontractor':
                    subcontractor_id = request.POST.get('subcontractor_id', '')
                    if subcontractor_id:
                        try:
                            sub = Subcontractor.objects.get(pk=subcontractor_id)
                            user.profile.subcontractors.add(sub)
                        except Subcontractor.DoesNotExist:
                            pass
                
                # 同步权限
                user.profile.sync_group_permissions()
            
            log_operation(request.user, '用户管理', action, f'{"新增" if action == "create" else "修改"}用户 {user.username}', str(user.pk))
            
            # 返回成功响应，包含随机密码（如果有）
            response_data = {'success': True, 'message': '保存成功'}
            if action == 'create' and random_pwd:
                response_data['random_password'] = random_pwd
                response_data['message'] = f'新用户 {user.username} 的初始密码为：{random_pwd}，请妥善保管并通知用户修改'
            
            return JsonResponse(response_data)
        
        except IntegrityError as e:
            logger.exception('用户保存失败：数据库完整性错误')
            return JsonResponse({'error': '保存失败：数据库错误（可能是重复的用户名或其他约束冲突）'}, status=400)
        except (DatabaseError, Exception) as e:
            logger.exception('用户保存失败：未知错误')
            return JsonResponse({'error': '保存失败：系统异常，请重试'}, status=500)
    
    return redirect('user_list')


@admin_required
@require_POST
def user_delete(request, pk):
    if request.user.pk == int(pk):
        return JsonResponse({'error': '不能删除自己'}, status=400)
    user = get_object_or_404(User, pk=pk)
    username = user.username
    user.delete()
    log_operation(request.user, '用户管理', 'delete', f'删除用户 {username}', str(pk))
    return JsonResponse({'success': True})


@admin_required
@require_GET
def user_detail_api(request, pk):
    user = get_object_or_404(User, pk=pk)
    # 始终返回用户的实际角色，而不是用户组信息
    role = user.profile.role if hasattr(user, 'profile') else 'clerk'
    
    subcontractor_id = ''
    if hasattr(user, 'profile') and role == 'subcontractor':
        sub = user.profile.subcontractors.first()
        if sub:
            subcontractor_id = str(sub.id)
    
    data = {
        'id': user.pk,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'is_active': user.is_active,
        'is_superuser': user.is_superuser,
        'role': role,
        'phone': user.profile.phone if hasattr(user, 'profile') else '',
        'subcontractor_id': subcontractor_id,
    }
    return JsonResponse(data)


@admin_required
def user_groups(request):
    """用户分组管理页面"""
    from ..models import Profile
    
    # 获取所有角色数据
    roles = []
    for role_code, role_name in Profile.ROLE_CHOICES:
        # 统计每个角色的用户数量
        user_count = Profile.objects.filter(role=role_code).count()
        roles.append({
            'code': role_code,
            'name': role_name,
            'user_count': user_count
        })
    
    context = {
        'roles': roles,
    }
    return render(request, 'inventory/user_groups.html', context)


# ========== 个人设置（所有已登录用户可用） ==========

@login_required
def profile_page(request):
    """个人设置页面"""
    return render(request, 'inventory/profile.html')


@login_required
@require_POST
def change_password(request):
    """修改密码"""
    old_password = request.POST.get('old_password', '')
    new_password = request.POST.get('new_password', '')
    confirm_password = request.POST.get('confirm_password', '')

    if not old_password or not new_password or not confirm_password:
        return JsonResponse({'error': '请填写所有密码字段'}, status=400)

    if not request.user.check_password(old_password):
        return JsonResponse({'error': '当前密码不正确'}, status=400)

    if len(new_password) < 8:
        return JsonResponse({'error': '新密码长度至少为 8 位'}, status=400)

    if new_password != confirm_password:
        return JsonResponse({'error': '两次输入的新密码不一致'}, status=400)

    if old_password == new_password:
        return JsonResponse({'error': '新密码不能与当前密码相同'}, status=400)

    request.user.set_password(new_password)
    request.user.save()

    # 更新 session，防止修改密码后被登出
    from django.contrib.auth import update_session_auth_hash
    update_session_auth_hash(request, request.user)

    log_operation(request.user, '个人设置', 'update', '修改密码')
    return JsonResponse({'success': True, 'message': '密码修改成功'})


@login_required
@require_POST
def update_profile(request):
    """更新个人信息"""
    user = request.user
    first_name = request.POST.get('first_name', '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone', '').strip()

    user.first_name = first_name
    user.email = email
    user.save(update_fields=['first_name', 'email'])

    if hasattr(user, 'profile'):
        user.profile.phone = phone
        user.profile.save(update_fields=['phone'])

    log_operation(user, '个人设置', 'update', '更新个人信息')
    return JsonResponse({'success': True, 'message': '个人信息已保存'})


# ========== 操作日志 ==========

@admin_required
def log_list(request):
    logs = OperationLog.objects.all()
    module_filter = request.GET.get('module', '')
    op_type_filter = request.GET.get('op_type', '')
    operator_filter = request.GET.get('operator', '')
    date_from = parse_date(request.GET.get('date_from', ''))
    date_to = parse_date(request.GET.get('date_to', ''))
    if module_filter:
        logs = logs.filter(module=module_filter)
    if op_type_filter:
        logs = logs.filter(op_type=op_type_filter)
    if operator_filter:
        logs = logs.filter(operator__icontains=operator_filter)
    if date_from:
        logs = logs.filter(time__date__gte=date_from)
    if date_to:
        logs = logs.filter(time__date__lte=date_to)

    from django.core.paginator import Paginator
    paginator = Paginator(logs, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 获取模块和操作类型选项用于筛选
    module_choices = OperationLog.objects.values_list('module', flat=True).distinct().order_by('module')
    op_type_choices = OperationLog.TYPE_CHOICES

    return render(request, 'inventory/log_list.html', {
        'logs': page_obj,
        'module_filter': module_filter,
        'op_type_filter': op_type_filter,
        'operator_filter': operator_filter,
        'date_from': date_from,
        'date_to': date_to,
        'module_choices': module_choices,
        'op_type_choices': op_type_choices,
        'page_obj': page_obj,
    })


# ========== 备份和恢复 ==========

@admin_required
@require_POST
def backup_data(request):

    MAX_BACKUP_ROWS = 50000

    data = {
        'timestamp': timezone.now().isoformat(),
        'projects': list(Project.all_objects.values()[:MAX_BACKUP_ROWS]),
        'categories': list(Category.all_objects.values()[:MAX_BACKUP_ROWS]),
        'materials': list(Material.objects.values()[:MAX_BACKUP_ROWS]),
        'suppliers': list(Supplier.all_objects.values()[:MAX_BACKUP_ROWS]),
        'inbound_records': list(InboundRecord.all_objects.values()[:MAX_BACKUP_ROWS]),
        'purchase_plans': list(PurchasePlan.all_objects.values()[:MAX_BACKUP_ROWS]),
        # 安全：显式列出用户字段白名单，绝不包含 password 字段。
        # 密码哈希属于敏感数据，即使是哈希值也不应出现在备份文件中，
        # 以防备份文件泄露后被用于离线暴力破解。修改此列表时请勿添加 password。
        'users': list(User.objects.values('id', 'username', 'first_name', 'last_name', 'email', 'is_active', 'is_superuser')[:MAX_BACKUP_ROWS]),
    }

    filename = f'backup_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
    response = HttpResponse(json.dumps(data, default=decimal_default, ensure_ascii=False, indent=2), content_type='application/json')
    response['Content-Disposition'] = make_attachment_disposition(filename)
    log_operation(request.user, '系统设置', 'export', '备份系统数据')
    return response


@admin_required
@require_POST
def restore_data(request):
    """从备份文件恢复数据"""
    # 每种模型允许恢复的字段白名单（不含 id、code 等主键/查找字段和 auto 字段）
    ALLOWED_FIELDS = {
        'categories': {'name', 'remark', 'is_deleted', 'deleted_at'},
        'projects': {
            'name', 'manager', 'location', 'start_date', 'end_date',
            'budget', 'status', 'remark', 'is_deleted', 'deleted_at',
        },
        'suppliers': {
            'name', 'contact', 'phone', 'address', 'main_type_id',
            'credit_rating', 'start_date', 'remark', 'is_deleted', 'deleted_at',
        },
        'materials': {
            'name', 'category_id', 'spec', 'unit',
            'standard_price', 'safety_stock', 'remark',
        },
        'inbound_records': {
            'project_id', 'material_id', 'date', 'quantity', 'unit_price',
            'total_amount', 'supplier_id', 'batch_no', 'inspector',
            'quality_status', 'location', 'spec', 'operator_id',
            'operate_time', 'remark', 'is_deleted', 'deleted_at',
        },
        'purchase_plans': {
            'project_id', 'material_id', 'quantity', 'unit_price',
            'total_amount', 'status', 'planned_date', 'remark',
            'operator_id', 'is_deleted', 'deleted_at',
        },
        'users': {
            'first_name', 'last_name', 'email', 'is_active', 'is_superuser',
        },
    }

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': '请选择备份文件'}, status=400)

    MAX_RESTORE_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    if file.size > MAX_RESTORE_FILE_SIZE:
        return JsonResponse({'error': '备份文件过大，最大支持 50MB'}, status=400)

    try:
        raw = file.read().decode('utf-8')
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': '无效的备份文件格式'}, status=400)

    if 'timestamp' not in data:
        return JsonResponse({'error': '无效的备份文件：缺少时间戳'}, status=400)

    restored = {}
    model_map = {
        'categories': (Category.all_objects, ALLOWED_FIELDS['categories']),
        'projects': (Project.all_objects, ALLOWED_FIELDS['projects']),
        'suppliers': (Supplier.all_objects, ALLOWED_FIELDS['suppliers']),
        'materials': (Material.objects, ALLOWED_FIELDS['materials']),
        'inbound_records': (InboundRecord.all_objects, ALLOWED_FIELDS['inbound_records']),
        'purchase_plans': (PurchasePlan.all_objects, ALLOWED_FIELDS['purchase_plans']),
        'users': (User.objects, ALLOWED_FIELDS['users']),
    }

    try:
        with transaction.atomic():
            for key, (manager, allowed) in model_map.items():
                if key not in data:
                    continue
                
                count = 0
                for item in data[key]:
                    # 用户通过 username 查找，入库记录和采购计划通过 no 查找，其他通过 code 查找
                    if key == 'users':
                        lookup_field = 'username'
                        lookup_value = item.get('username')
                    elif key in ('inbound_records', 'purchase_plans'):
                        lookup_field = 'no'
                        lookup_value = item.get('no')
                    else:
                        lookup_field = 'code'
                        lookup_value = item.get('code')
                    
                    if not lookup_value:
                        continue
                    
                    # 仅保留白名单内的字段，防止注入非法字段
                    defaults = {k: v for k, v in item.items() if k in allowed}
                    manager.update_or_create(**{lookup_field: lookup_value}, defaults=defaults)
                    count += 1
                restored[key] = count

    except (IntegrityError, DatabaseError) as e:
        logger.exception('数据恢复失败：数据库操作异常')
        return JsonResponse({'error': '数据恢复失败：数据库操作异常，已回滚所有更改'}, status=500)
    except (ValueError, TypeError, KeyError) as e:
        logger.exception('数据恢复失败：备份文件数据格式错误')
        return JsonResponse({'error': '数据恢复失败：备份文件中包含无效数据，已回滚所有更改'}, status=400)

    summary = ', '.join(f'{k}: {v}条' for k, v in restored.items())
    log_operation(request.user, '系统设置', 'other', f'从备份恢复数据：{summary}')
    return JsonResponse({
        'success': True,
        'message': f'数据恢复成功：{summary}',
        'restored': restored,
    })


@admin_required
@require_GET
def subcontract_category_list_api(request):
    """清单分类列表API"""
    from ..models import SubcontractCategory
    categories = SubcontractCategory.objects.all().order_by('category_code')
    data = []
    for cat in categories:
        data.append({
            'id': cat.pk,
            'code': cat.category_code,
            'name': cat.category_name
        })
    return JsonResponse(data, safe=False)


@admin_required
@require_POST
def init_subcontract_categories(request):
    """一键初始化清单分类"""
    if request.method == 'POST':
        try:
            from ..models import SubcontractCategory
            # 定义主要清单分类
            categories = [
                {'category_code': 'BAT0001', 'category_name': '基础工程'},
                {'category_code': 'BAT0002', 'category_name': '房屋建筑'},
                {'category_code': 'BAT0003', 'category_name': '市政工程'},
                {'category_code': 'BAT0004', 'category_name': '特种加固'},
                {'category_code': 'BAT0005', 'category_name': '装饰装修'},
            ]
            
            created_count = 0
            skipped_count = 0
            
            with transaction.atomic():
                for cat_data in categories:
                    # 检查是否已存在同编号的清单分类（包括软删除的）
                    existing_cat = SubcontractCategory.all_objects.filter(category_code=cat_data['category_code']).first()
                    if existing_cat:
                        if existing_cat.is_deleted:
                            # 恢复软删除的分类
                            existing_cat.is_deleted = False
                            existing_cat.save()
                            created_count += 1
                        else:
                            # 跳过已存在的分类
                            skipped_count += 1
                        continue
                    
                    # 创建分类
                    SubcontractCategory.objects.create(
                        category_code=cat_data['category_code'],
                        category_name=cat_data['category_name'],
                        remark='系统初始化创建'
                    )
                    created_count += 1
            
            log_operation(request.user, '系统设置', 'create', 
                         f'一键初始化清单分类：创建{created_count}个，跳过{skipped_count}个')
            
            return JsonResponse({
                'success': True, 
                'message': f'清单分类初始化完成：创建{created_count}个，跳过{skipped_count}个（已存在）'
            })
            
        except (IntegrityError, DatabaseError) as e:
            logger.exception('初始化清单分类失败：数据库操作异常')
            return JsonResponse({'error': '初始化失败：数据库操作异常'}, status=500)
        except Exception as e:
            logger.exception('初始化清单分类失败：未知错误')
            return JsonResponse({'error': '初始化失败：系统异常，请重试'}, status=500)
    return JsonResponse({'error': '无效请求'}, status=400)


@admin_required
@require_POST
def clear_all_data(request):
    """一键清空所有数据"""
    if request.method == 'POST':
        confirm = request.POST.get('confirm', '').strip()
        if confirm != 'CONFIRM':
            return JsonResponse({'error': '请输入 CONFIRM 确认清空所有数据'}, status=400)
        
        try:
            with transaction.atomic():
                # 按照依赖关系的顺序删除数据
                # 1. 删除操作日志
                OperationLog.objects.all().delete()
                # 2. 删除入库记录
                InboundRecord.all_objects.all().hard_delete()
                # 3. 删除发货单
                from ..models import Delivery
                Delivery.all_objects.all().hard_delete()
                # 4. 删除采购计划
                PurchasePlan.all_objects.all().hard_delete()
                # 5. 删除材料
                Material.objects.all().delete()
                # 6. 删除供应商
                Supplier.all_objects.all().hard_delete()
                # 7. 删除项目
                Project.all_objects.all().hard_delete()
                # 8. 删除分类
                Category.all_objects.all().hard_delete()
                # 9. 删除清单分类
                from ..models import SubcontractList
                SubcontractList.all_objects.all().hard_delete()
                # 10. 保留用户数据和角色信息，只清除其他扩展信息
                # 保存当前用户的角色信息
                current_user_id = request.user.id
                profiles_data = []
                for profile in Profile.objects.all():
                    profiles_data.append({
                        'user_id': profile.user_id,
                        'role': profile.role,
                        'phone': profile.phone,
                    })
                # 删除所有 Profile
                Profile.objects.all().delete()
                # 重新创建 Profile，保留角色信息
                for data in profiles_data:
                    Profile.objects.create(
                        user_id=data['user_id'],
                        role=data['role'],
                        phone=data['phone'],
                    )
                
            log_operation(request.user, '系统设置', 'other', '清空所有数据')
            return JsonResponse({'success': True, 'message': '所有数据已清空，用户角色信息已保留'})
        except (IntegrityError, DatabaseError) as e:
            logger.exception('清空数据失败：数据库操作异常')
            return JsonResponse({'error': '清空数据失败：数据库操作异常，已回滚所有更改'}, status=500)
        except Exception as e:
            logger.exception('清空数据失败：未知错误')
            return JsonResponse({'error': '清空数据失败：系统异常，请重试'}, status=500)
    return JsonResponse({'error': '无效请求'}, status=400)


@admin_required
@require_POST
def init_categories(request):
    """一键初始化材料分类"""
    if request.method == 'POST':
        try:
            from ..models import Category
            # 定义主要材料分类
            categories = [
                {'name': '钢筋'},
                {'name': '水泥'},
                {'name': '混凝土'},
                {'name': '砂石'},
                {'name': '钢绞线'},
                {'name': '钢管'},
                {'name': '水泵'},
            ]
            
            created_count = 0
            skipped_count = 0
            
            with transaction.atomic():
                for cat_data in categories:
                    # 检查是否已存在同名分类（包括软删除的）
                    existing_cat = Category.all_objects.filter(name=cat_data['name']).first()
                    if existing_cat:
                        if existing_cat.is_deleted:
                            # 恢复软删除的分类
                            existing_cat.is_deleted = False
                            existing_cat.save()
                            created_count += 1
                        else:
                            # 跳过已存在的分类
                            skipped_count += 1
                        continue
                    
                    # 生成编码：CAT0001形式
                    # 找到当前最大的编码
                    last_cat = Category.all_objects.filter(code__startswith='CAT').order_by('-code').first()
                    if last_cat:
                        # 提取数字部分并加1
                        try:
                            last_num = int(last_cat.code[3:])
                            new_num = last_num + 1
                        except (ValueError, IndexError):
                            new_num = 1
                    else:
                        new_num = 1
                    
                    # 生成新编码
                    code = f"CAT{new_num:04d}"
                    # 确保编码唯一
                    while Category.all_objects.filter(code=code).exists():
                        new_num += 1
                        code = f"CAT{new_num:04d}"
                    
                    # 创建分类
                    Category.objects.create(
                        code=code,
                        name=cat_data['name'],
                        remark='系统初始化创建'
                    )
                    created_count += 1
            
            log_operation(request.user, '系统设置', 'create', 
                         f'一键初始化材料分类：创建{created_count}个，跳过{skipped_count}个')
            
            return JsonResponse({
                'success': True, 
                'message': f'材料分类初始化完成：创建{created_count}个，跳过{skipped_count}个（已存在）'
            })
            
        except (IntegrityError, DatabaseError) as e:
            logger.exception('初始化材料分类失败：数据库操作异常')
            return JsonResponse({'error': '初始化失败：数据库操作异常'}, status=500)
        except Exception as e:
            logger.exception('初始化材料分类失败：未知错误')
            return JsonResponse({'error': '初始化失败：系统异常，请重试'}, status=500)
    
    return JsonResponse({'error': '无效请求'}, status=400)
