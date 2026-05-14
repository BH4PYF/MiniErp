import json
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.db.models import Count
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction, IntegrityError, DatabaseError
from django.utils import timezone

from ..models import (
    Profile, Project, Category, Material, Supplier,
    InboundRecord, OperationLog, SystemSetting, PurchasePlan,
    Delivery, Subcontractor, SubcontractCategory, SubcontractList,
    Budget, BudgetItem, Contract, ContractItem,
    Measurement, MeasurementItem, Settlement, SettlementItem,
    MaterialPlan,
)
from .utils import (
    admin_required, log_operation,
    generate_code, decimal_default,
    make_attachment_disposition,
)

logger = logging.getLogger('inventory')


# ========== 系统设置 ==========

@admin_required
def settings_page(request):
    """系统设置页面"""
    import sys
    import django

    company_name = SystemSetting.get_setting('company_name', '材料管理系统 V1.8')

    login_max_attempts = int(SystemSetting.get_setting('login_max_attempts', '5'))
    login_lockout_seconds = int(SystemSetting.get_setting('login_lockout_seconds', '300'))
    login_lockout_minutes = login_lockout_seconds // 60

    django_version = django.get_version()
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

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

    system_version = 'V2.0.0'
    system_build = '20260414'

    # 钉钉配置
    dingtalk_push_mode = SystemSetting.get_setting('dingtalk_push_mode', 'off')
    dingtalk_robot_token = SystemSetting.get_setting('dingtalk_robot_token', '')
    dingtalk_robot_secret = SystemSetting.get_setting('dingtalk_robot_secret', '')
    dingtalk_app_key = SystemSetting.get_setting('dingtalk_app_key', '')
    dingtalk_app_secret = SystemSetting.get_setting('dingtalk_app_secret', '')
    dingtalk_agent_id = SystemSetting.get_setting('dingtalk_agent_id', '')

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
        'dingtalk_push_mode': dingtalk_push_mode,
        'dingtalk_robot_token': dingtalk_robot_token,
        'dingtalk_robot_secret': dingtalk_robot_secret,
        'dingtalk_app_key': dingtalk_app_key,
        'dingtalk_app_secret': dingtalk_app_secret,
        'dingtalk_agent_id': dingtalk_agent_id,
    })


@admin_required
@require_GET
def settings_users_api(request):
    """AJAX 加载用户与权限 Tab 数据"""
    from django.contrib.auth.models import Group

    users = User.objects.select_related('profile').all().order_by('username')
    users_without_profile = [u for u in users if not hasattr(u, 'profile')]
    if users_without_profile:
        Profile.objects.bulk_create(
            [Profile(user=u) for u in users_without_profile],
            ignore_conflicts=True,
        )
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
def save_system_settings(request):
    """保存系统设置（导航栏标题）"""
    if request.method == 'POST':
        company_name = request.POST.get('company_name', '').strip()

        if company_name:
            SystemSetting.set_setting('company_name', company_name, '公司/项目名称')

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

            if not (1 <= login_max_attempts <= 10):
                return JsonResponse({'error': '最大登录尝试次数必须在 1-10 之间'}, status=400)
            if not (1 <= login_lockout_minutes <= 60):
                return JsonResponse({'error': '锁定时长必须在 1-60 分钟之间'}, status=400)

            login_lockout_seconds = login_lockout_minutes * 60

            SystemSetting.set_setting('login_max_attempts', str(login_max_attempts), '最大登录尝试次数')
            SystemSetting.set_setting('login_lockout_seconds', str(login_lockout_seconds), '登录锁定时间（秒）')

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


# ========== 分类管理 ==========

@admin_required
def add_custom_category(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        remark = request.POST.get('remark', '').strip()
        category_type = request.POST.get('category_type', 'material')
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
    category_code = obj.category_code
    category_name = obj.category_name
    obj.delete()
    log_operation(request.user, '清单分类', 'delete', f'删除清单分类 {category_code} {category_name}', category_code)
    return JsonResponse({'success': True})


@admin_required
@require_GET
def subcontract_category_list_api(request):
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
    if request.method == 'POST':
        try:
            from ..models import SubcontractCategory
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
                    existing_cat = SubcontractCategory.all_objects.filter(category_code=cat_data['category_code']).first()
                    if existing_cat:
                        if existing_cat.is_deleted:
                            existing_cat.is_deleted = False
                            existing_cat.save()
                            created_count += 1
                        else:
                            skipped_count += 1
                        continue

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
def init_categories(request):
    """一键初始化材料分类"""
    if request.method == 'POST':
        try:
            from ..models import Category
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
                    existing_cat = Category.all_objects.filter(name=cat_data['name']).first()
                    if existing_cat:
                        if existing_cat.is_deleted:
                            existing_cat.is_deleted = False
                            existing_cat.save()
                            created_count += 1
                        else:
                            skipped_count += 1
                        continue

                    last_cat = Category.all_objects.filter(code__startswith='CAT').order_by('-code').first()
                    if last_cat:
                        try:
                            last_num = int(last_cat.code[3:])
                            new_num = last_num + 1
                        except (ValueError, IndexError):
                            new_num = 1
                    else:
                        new_num = 1

                    code = f"CAT{new_num:04d}"
                    while Category.all_objects.filter(code=code).exists():
                        new_num += 1
                        code = f"CAT{new_num:04d}"

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

    filename = f'backup_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
    response = HttpResponse(json.dumps(data, default=decimal_default, ensure_ascii=False, indent=2), content_type='application/json')
    response['Content-Disposition'] = make_attachment_disposition(filename)
    log_operation(request.user, '系统设置', 'export', '备份系统数据')
    return response


@admin_required
@require_POST
def restore_data(request):
    """从备份文件恢复数据"""
    ALLOWED_FIELDS = {
        'categories': {'name', 'remark', 'is_deleted', 'deleted_at'},
        'projects': {
            'name', 'manager', 'start_date', 'end_date',
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
            'quality_status', 'spec', 'operator_id',
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

    MAX_RESTORE_FILE_SIZE = 50 * 1024 * 1024
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
@require_POST
def clear_all_data(request):
    """一键清空所有数据"""
    if request.method == 'POST':
        confirm = request.POST.get('confirm', '').strip()
        if confirm != 'CONFIRM':
            return JsonResponse({'error': '请输入 CONFIRM 确认清空所有数据'}, status=400)

        try:
            with transaction.atomic():
                OperationLog.objects.all().delete()
                InboundRecord.all_objects.all().hard_delete()
                Delivery.all_objects.all().hard_delete()
                PurchasePlan.all_objects.all().hard_delete()
                Material.objects.all().delete()
                Supplier.all_objects.all().hard_delete()
                Project.all_objects.all().hard_delete()
                Category.all_objects.all().hard_delete()
                SubcontractList.all_objects.all().hard_delete()

                current_user_id = request.user.id
                profiles_data = []
                for profile in Profile.objects.all():
                    profiles_data.append({
                        'user_id': profile.user_id,
                        'role': profile.role,
                        'phone': profile.phone,
                    })
                Profile.objects.all().delete()
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
def save_dingtalk_config(request):
    """保存钉钉推送配置。"""
    push_mode = request.POST.get('push_mode', 'off')
    robot_token = request.POST.get('robot_token', '').strip()
    robot_secret = request.POST.get('robot_secret', '').strip()
    app_key = request.POST.get('app_key', '').strip()
    app_secret = request.POST.get('app_secret', '').strip()
    agent_id = request.POST.get('agent_id', '').strip()

    if push_mode not in ('robot', 'app', 'off'):
        return JsonResponse({'error': '无效的推送模式'}, status=400)
    if push_mode == 'robot' and not robot_token:
        return JsonResponse({'error': '机器人模式需要填写 Webhook Token'}, status=400)
    if push_mode == 'app' and not (app_key and app_secret and agent_id):
        return JsonResponse({'error': '应用模式需要填写 AppKey、AppSecret 和 AgentId'}, status=400)

    try:
        SystemSetting.set_setting('dingtalk_push_mode', push_mode, '钉钉推送方式：robot/app/off')
        SystemSetting.set_setting('dingtalk_robot_token', robot_token, '钉钉机器人 Webhook Token')
        SystemSetting.set_setting('dingtalk_robot_secret', robot_secret, '钉钉机器人签名密钥')
        SystemSetting.set_setting('dingtalk_app_key', app_key, '钉钉自建应用 AppKey')
        SystemSetting.set_setting('dingtalk_app_secret', app_secret, '钉钉自建应用 AppSecret')
        SystemSetting.set_setting('dingtalk_agent_id', agent_id, '钉钉自建应用 AgentId')

        SystemSetting.objects.filter(key='dingtalk_access_token').delete()
        SystemSetting.objects.filter(key='dingtalk_token_expire').delete()

        log_operation(request.user, '系统设置', 'update', f'更新钉钉推送配置（模式: {push_mode}）')
        return JsonResponse({'success': True, 'message': '钉钉推送配置已保存'})
    except (IntegrityError, DatabaseError) as e:
        logger.exception('保存钉钉配置失败')
        return JsonResponse({'error': '保存失败：数据库异常'}, status=500)


@admin_required
@require_POST
def dingtalk_test(request):
    """发送钉钉测试消息。"""
    message = request.POST.get('message', '这是一条来自 MiniErp 的测试消息')

    from ..services.dingtalk import DingTalkService, DingTalkError

    push_mode = SystemSetting.get_setting('dingtalk_push_mode', 'off')
    if push_mode == 'off':
        return JsonResponse({'error': '钉钉推送未启用，请先在配置中启用'}, status=400)

    try:
        if push_mode == 'robot':
            DingTalkService.send_robot_text(message)
        elif push_mode == 'app':
            DingTalkService.send_app_text(request.user.username, message)
        return JsonResponse({'success': True, 'message': '测试消息发送成功'})
    except DingTalkError as e:
        logger.exception('钉钉测试消息发送失败')
        return JsonResponse({'error': f'发送失败：{e}'}, status=500)
    except Exception as e:
        logger.exception('钉钉测试消息发送异常')
        return JsonResponse({'error': f'发送异常：{e}'}, status=500)
