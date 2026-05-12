import logging
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse

from ..models import Profile, SystemSetting
from ..services.rate_limit_service import (
    clear_login_attempts,
    get_client_ip,
    get_login_attempts,
    get_login_lockout_seconds,
    get_login_max_attempts,
    increment_login_attempts,
)
from .utils import is_ajax_request, log_operation

logger = logging.getLogger('inventory')

# ========== 登录/登出 ==========

def login_view(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'profile') and request.user.profile.role == 'supplier':
            return redirect('delivery_list')
        if hasattr(request.user, 'profile') and request.user.profile.role == 'subcontractor':
            return redirect('measurement_list')
        return redirect('dashboard')
    
    # 获取导航栏标题（用于登录页面显示）
    navbar_title = SystemSetting.get_setting('company_name', '材料管理系统')
    
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        
        # 获取客户端 IP 地址
        ip_address = get_client_ip(request)

        # 检查登录限流（同时检查用户名和 IP）
        max_attempts = get_login_max_attempts()
        lockout_seconds = get_login_lockout_seconds()
        attempts = get_login_attempts(username, ip_address)
        if attempts >= max_attempts:
            remaining = lockout_seconds // 60
            # 如果是 AJAX 请求，返回 JSON
            if is_ajax_request(request):
                return JsonResponse({'error': f'登录尝试次数过多，请 {remaining} 分钟后再试'}, status=400)
            messages.error(request, f'登录尝试次数过多，请 {remaining} 分钟后再试')
            logger.warning('登录限流触发：用户 %s (IP: %s) 已被锁定', username, ip_address)
            return render(request, 'login.html', {'navbar_title': navbar_title})

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                # 如果是 AJAX 请求，返回 JSON
                if is_ajax_request(request):
                    return JsonResponse({'error': '该账户已被禁用'}, status=400)
                messages.error(request, '该账户已被禁用')
                return render(request, 'login.html', {'navbar_title': navbar_title})
            login(request, user)
            clear_login_attempts(username, ip_address)
            if not hasattr(user, 'profile'):
                Profile.objects.create(user=user, role='admin' if user.is_superuser else 'management')
            log_operation(user, '系统', 'login', f'{user.username} 登录系统')
            # 如果是 AJAX 请求，返回成功响应
            if is_ajax_request(request):
                if user.profile.role == 'supplier':
                    redirect_url = 'delivery_list'
                else:
                    redirect_url = 'dashboard'
                return JsonResponse({'success': True, 'message': '登录成功', 'redirect_url': redirect_url})
            if user.profile.role == 'supplier':
                return redirect('delivery_list')
            return redirect('dashboard')

        increment_login_attempts(username, ip_address)
        remaining_attempts = max_attempts - get_login_attempts(username, ip_address)
        error_msg = f'用户名或密码错误，还可尝试 {remaining_attempts} 次' if remaining_attempts > 0 else f'登录尝试次数过多，请 {lockout_seconds // 60} 分钟后再试'
        
        # 如果是 AJAX 请求，返回 JSON
        if is_ajax_request(request):
            return JsonResponse({'error': error_msg}, status=400)
        
        messages.error(request, error_msg)
        logger.warning('登录失败：用户 %s (IP: %s)', username, ip_address)
    return render(request, 'login.html', {'navbar_title': navbar_title})


def logout_view(request):
    if request.method != 'POST':
        return redirect('dashboard')
    if request.user.is_authenticated:
        log_operation(request.user, '系统', 'other', f'{request.user.username} 登出系统')
    logout(request)
    return redirect('login')
