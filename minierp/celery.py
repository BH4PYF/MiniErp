"""Celery配置模块"""
import os
import logging
from celery import Celery
from django.conf import settings

logger = logging.getLogger('celery')

# 设置Django设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'minierp.settings')

# 创建Celery实例
app = Celery('minierp')

# 使用Django设置配置Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现任务
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """调试任务"""
    logger.debug('Request: %r', self.request)
