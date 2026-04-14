import os
import multiprocessing

# Gunicorn配置
bind = "0.0.0.0:6666"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
timeout = 30
keepalive = 2

# 日志配置
accesslog = os.path.join(os.path.dirname(__file__), 'logs', 'gunicorn_access.log')
errorlog = os.path.join(os.path.dirname(__file__), 'logs', 'gunicorn_error.log')
loglevel = 'info'

# 进程名称
proc_name = 'material-system'

# 最大请求数
max_requests = 1000
max_requests_jitter = 100

# 工作进程最大并发客户端数
worker_connections = 1000

# 每个工作进程的线程数
threads = 2
