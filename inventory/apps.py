from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = 'inventory'

    # Prometheus 业务指标已于 2026-10-04 移除。
    # 原 ready() 中调用的 inventory.metrics.connect_signals() 从未真正产生价值：
    # /metrics/ 端点自加入起从未被 Prometheus 成功抓取过一次（详见 urls.py 注释），
    # 且进程内 Counter 在 gunicorn 多 worker 下也无法表示真实业务总量。
    # 如日后确需监控，请改用 django-prometheus 并从数据库聚合业务量。
