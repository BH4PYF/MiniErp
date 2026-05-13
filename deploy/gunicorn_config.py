import os
import multiprocessing

# Gunicorn 配置 — 针对 I/O 密集型 Django 应用优化
bind = "0.0.0.0:6666"

# worker 数量：I/O 密集型应用，2-4 × CPU 核数通常最优
# 使用 gthread 后每个 worker 内部还有线程池，总数可适度降低
workers = min(multiprocessing.cpu_count() * 2 + 1, 8)

# gthread：异步 worker，每个 worker 内多个线程处理并发请求
# Django 的数据库查询会释放 GIL，线程模型对 I/O 密集型负载效率更高
worker_class = "gthread"
threads = 4

# 连接相关
timeout = 60
graceful_timeout = 30
keepalive = 5

# 预加载应用代码，减少每个 worker 的内存开销和启动时间
preload_app = True

# 日志配置
accesslog = os.path.join(os.path.dirname(__file__), 'logs', 'gunicorn_access.log')
errorlog = os.path.join(os.path.dirname(__file__), 'logs', 'gunicorn_error.log')
loglevel = 'info'

# 进程名称
proc_name = 'material-system'

# 每个 worker 处理一定请求后自动重启，防止内存泄漏积累
max_requests = 2000
max_requests_jitter = 200
