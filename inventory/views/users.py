import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction, IntegrityError, DatabaseError
from django.views.decorators.http import require_GET, require_POST

from ..models import Profile, OperationLog, Subcontractor
from .utils import admin_required, log_operation, parse_date

logger = logging.getLogger('inventory')


# ========== 用户管理 ==========

@admin_required
def user_list(request):
    users = User.objects.select_related('profile').prefetch_related('groups').order_by('id')
    groups = Group.objects.all().order_by('name')

    role_list = []
    for role_code, role_name in Profile.ROLE_CHOICES:
        if role_code != 'admin':
            role_list.append({'code': role_code, 'name': role_name})

    subcontractors = Subcontractor.objects.all()

    return render(request, 'inventory/user_list.html', {
        'users': users, 'role_list': role_list, 'subcontractors': subcontractors
    })


@admin_required
def user_save(request):
    if request.method == 'POST':
        pk = request.POST.get('id')
        if pk:
            user = get_object_or_404(User, pk=pk)
            action = 'update'
        else:
            user = User()
            action = 'create'

        username = request.POST.get('username', '').strip()
        if not username:
            return JsonResponse({'error': '用户名不能为空'})

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

        password = request.POST.get('password', '')
        random_pwd = None
        if password:
            if len(password) < 8:
                return JsonResponse({'error': '密码长度至少为 8 位'})
            user.set_password(password)
        elif action == 'create':
            import secrets
            random_pwd = secrets.token_urlsafe(12)
            user.set_password(random_pwd)

        try:
            with transaction.atomic():
                user.save()
                if not hasattr(user, 'profile'):
                    Profile.objects.create(user=user)

                role = request.POST.get('role', 'management')
                role_name_to_code = {role_name: role_code for role_code, role_name in Profile.ROLE_CHOICES}
                role_code_to_name = {role_code: role_name for role_code, role_name in Profile.ROLE_CHOICES}

                if role.startswith('group_'):
                    user.groups.clear()
                    group_id = role.split('_')[1]
                    try:
                        group = Group.objects.get(id=group_id)
                        user.groups.add(group)
                        if group.name in role_name_to_code:
                            user.profile.role = role_name_to_code[group.name]
                        else:
                            user.profile.role = 'management'
                    except Group.DoesNotExist:
                        pass
                else:
                    user.groups.clear()
                    user.profile.role = role

                    if role in role_code_to_name:
                        role_name = role_code_to_name[role]
                        try:
                            group = Group.objects.get(name=role_name)
                            user.groups.add(group)
                        except Group.DoesNotExist:
                            pass

                user.profile.phone = request.POST.get('phone', '')
                user.profile.save()

                user.profile.subcontractors.clear()
                if role == 'subcontractor':
                    subcontractor_id = request.POST.get('subcontractor_id', '')
                    if subcontractor_id:
                        try:
                            sub = Subcontractor.objects.get(pk=subcontractor_id)
                            user.profile.subcontractors.add(sub)
                        except Subcontractor.DoesNotExist:
                            pass

                user.profile.sync_group_permissions()

            log_operation(request.user, '用户管理', action, f'{"新增" if action == "create" else "修改"}用户 {user.username}', str(user.pk))

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
    role = user.profile.role if hasattr(user, 'profile') else 'management'

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
    roles = []
    for role_code, role_name in Profile.ROLE_CHOICES:
        user_count = Profile.objects.filter(role=role_code).count()
        roles.append({
            'code': role_code,
            'name': role_name,
            'user_count': user_count
        })

    return render(request, 'inventory/user_groups.html', {'roles': roles})


# ========== 个人设置 ==========

@login_required
def profile_page(request):
    return render(request, 'inventory/profile.html')


@login_required
@require_POST
def change_password(request):
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

    from django.contrib.auth import update_session_auth_hash
    update_session_auth_hash(request, request.user)

    log_operation(request.user, '个人设置', 'update', '修改密码')
    return JsonResponse({'success': True, 'message': '密码修改成功'})


@login_required
@require_POST
def update_profile(request):
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
