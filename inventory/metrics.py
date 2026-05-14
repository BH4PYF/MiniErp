"""
Prometheus 业务指标定义

指标清单：
- erp_orders_total          Counter  按 type 标签（purchase/shipment/inbound/settlement）
- erp_active_users          Gauge    当前活跃用户数
- erp_db_connections        Gauge    数据库连接数
- erp_celery_queue_length   Gauge    Celery 队列待处理任务数
"""

from prometheus_client import Counter, Gauge


# ---------------------------------------------------------------------------
# Counter：业务单据创建量，按类型区分
# ---------------------------------------------------------------------------
ERP_ORDERS_TOTAL = Counter(
    'erp_orders',
    'Total number of business orders created',
    ['type'],
)

# ---------------------------------------------------------------------------
# Gauge：运行时快照指标（在 /metrics/ 视图中按需刷新）
# ---------------------------------------------------------------------------
ERP_ACTIVE_USERS = Gauge(
    'erp_active_users',
    'Number of currently active users',
)

ERP_DB_CONNECTIONS = Gauge(
    'erp_db_connections',
    'Number of database connections',
)

ERP_CELERY_QUEUE_LENGTH = Gauge(
    'erp_celery_queue_length',
    'Number of pending tasks in Celery queues',
)


# ---------------------------------------------------------------------------
# Gauge 刷新函数
# ---------------------------------------------------------------------------

def refresh_gauges():
    """
    刷新所有 Gauge 型指标的最新值。

    在 /metrics/ 视图中调用此函数，再执行 generate_latest()，
    确保每次抓取时返回的都是当前时刻的瞬时值。
    """
    _refresh_active_users()
    _refresh_db_connections()
    _refresh_celery_queue_length()


def _refresh_active_users():
    """刷新活跃用户数（已登录且 session 未过期的用户）"""
    try:
        from django.contrib.sessions.models import Session
        from django.utils import timezone
        from importlib import import_module
        from django.conf import settings

        engine = import_module(settings.SESSION_ENGINE)
        session_store = engine.SessionStore

        sessions = Session.objects.filter(expire_date__gte=timezone.now())
        active_count = 0
        for session in sessions:
            data = session.get_decoded()
            if data.get('_auth_user_id'):
                active_count += 1
        ERP_ACTIVE_USERS.set(active_count)
    except Exception:
        ERP_ACTIVE_USERS.set(0)


def _refresh_db_connections():
    """刷新数据库连接数"""
    try:
        from django.db import connections
        # connections.all() 返回所有已配置的连接别名列表
        conn_count = len(connections.all())
        ERP_DB_CONNECTIONS.set(conn_count)
    except Exception:
        ERP_DB_CONNECTIONS.set(0)


def _refresh_celery_queue_length():
    """刷新 Celery 队列待处理任务数（处理 Celery 不可用的情况）"""
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        if inspect is None:
            ERP_CELERY_QUEUE_LENGTH.set(0)
            return

        active_stats = inspect.active()
        if active_stats is None:
            ERP_CELERY_QUEUE_LENGTH.set(0)
            return

        total = sum(len(tasks) for tasks in active_stats.values())
        ERP_CELERY_QUEUE_LENGTH.set(total)
    except Exception:
        ERP_CELERY_QUEUE_LENGTH.set(0)


# ---------------------------------------------------------------------------
# Django Signal 处理器：在关键模型创建时自动递增 Counter
# ---------------------------------------------------------------------------

def _on_purchase_plan_created(sender, instance, created, **kwargs):
    if created:
        ERP_ORDERS_TOTAL.labels(type='purchase').inc()


def _on_delivery_created(sender, instance, created, **kwargs):
    if created:
        ERP_ORDERS_TOTAL.labels(type='shipment').inc()


def _on_settlement_created(sender, instance, created, **kwargs):
    if created:
        ERP_ORDERS_TOTAL.labels(type='settlement').inc()


def connect_signals():
    """
    将信号处理器连接到对应模型的 post_save 信号。

    Django 文档推荐在 AppConfig.ready() 中调用此函数，
    以避免信号被重复注册。
    """
    from django.db.models.signals import post_save
    from inventory.models import PurchasePlan, Delivery, Settlement

    post_save.connect(_on_purchase_plan_created, sender=PurchasePlan, dispatch_uid='metrics_purchase_plan')
    post_save.connect(_on_delivery_created, sender=Delivery, dispatch_uid='metrics_delivery')
    post_save.connect(_on_settlement_created, sender=Settlement, dispatch_uid='metrics_settlement')
