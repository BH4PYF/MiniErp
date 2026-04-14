"""
Django settings for minierp project.
项目管理系统
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

_logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 提前定义 DEBUG，供后续 Sentry 等组件使用
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# 初始化 Sentry（生产环境错误追踪）
SENTRY_DSN = os.getenv('SENTRY_DSN', '')
if SENTRY_DSN and not DEBUG:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
        ],
        # 设置采样率
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
        profiles_sample_rate=float(os.getenv('SENTRY_PROFILES_SAMPLE_RATE', '0.1')),
        # 发送默认 PII（个人身份信息）
        send_default_pii=True,
        # 性能监控
        _experiments={
            "continuous_profiling_auto_start": True,
        },
        # 环境标识
        environment=os.getenv('SENTRY_ENVIRONMENT', 'production'),
        release=f'minierp@{os.getenv("APP_VERSION", "dev")}',
    )

BASE_DIR = Path(__file__).resolve().parent.parent

# 确保日志目录存在
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

# 从环境变量读取配置
_secret_key = os.getenv('SECRET_KEY', '')
if not _secret_key or _secret_key.startswith('django-insecure'):
    if os.getenv('DEBUG', 'True').lower() != 'true':
        raise ValueError(
            '生产环境必须设置安全的 SECRET_KEY。'
            '请运行: python -c "import secrets; print(secrets.token_urlsafe(50))" '
            '并将结果写入 .env 文件的 SECRET_KEY 字段。'
        )
    _secret_key = _secret_key or 'django-insecure-dev-only-do-not-use-in-production'
SECRET_KEY = _secret_key
# ALLOWED_HOSTS 配置：支持通配符和具体 IP
# 开发环境：允许所有主机访问（仅限 DEBUG=True）
# 生产环境：必须明确指定允许的域名/IP
# 安全配置：根据环境设置允许的主机
if DEBUG:
    # 开发环境：允许所有主机访问
    ALLOWED_HOSTS = ['*']
else:
    # 生产环境：只允许指定的域名和IP访问
    ALLOWED_HOSTS = [
        'erp.sdyhjzgc.com',
        'www.erp.sdyhjzgc.com',
        'localhost',
        '127.0.0.1',
        '::1',
    ]
    # 从环境变量读取额外的允许主机
    additional_hosts = os.getenv('ALLOWED_HOSTS_EXTRA', '')
    if additional_hosts:
        ALLOWED_HOSTS.extend([host.strip() for host in additional_hosts.split(',') if host.strip()])

# 内部 IP 列表（用于 django-debug-toolbar）
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]

INSTALLED_APPS = [
    # 主题必须放在最前面
    'admin_interface',
    'colorfield',
    # Django 自带
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # API框架
    'rest_framework',
    'django_filters',
    # 静态资源压缩
    'compressor',
    # 自定义应用
    'inventory',
]



# 主题配置
# admin_interface 使用 iframe 加载主题预览，需要允许同源嵌入
X_FRAME_OPTIONS = 'SAMEORIGIN'
# 静默 security.W019: 该警告要求 X_FRAME_OPTIONS='DENY'，
# 但 admin_interface 依赖 SAMEORIGIN 才能正常工作
SILENCED_SYSTEM_CHECKS = ['security.W019']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if DEBUG:
    # 开发环境：添加性能分析中间件（可选）
    MIDDLEWARE.append('minierp.middleware.ProfileMiddleware')
else:
    # 生产环境：启用慢请求监控中间件
    MIDDLEWARE.append('minierp.middleware.SlowRequestMiddleware')

ROOT_URLCONF = 'minierp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # 自定义全局设置
                'inventory.context_processors.global_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'minierp.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'material_system'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    # 自定义密码验证器，要求密码包含大小写字母、数字和特殊字符
    {
        'NAME': 'minierp.validators.CustomPasswordValidator',
        'OPTIONS': {
            'min_length': 12,
            'require_uppercase': True,
            'require_lowercase': True,
            'require_digit': True,
            'require_special': True,
        }
    },
]

LANGUAGE_CODE = os.getenv('LANGUAGE_CODE', 'zh-hans')
TIME_ZONE = os.getenv('TIME_ZONE', 'Asia/Shanghai')
USE_I18N = True
USE_TZ = True  # 启用时区支持，Django 官方建议，跨时区部署必备

# 静态文件配置
STATIC_URL = os.getenv('STATIC_URL', '/static/')
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# 静态文件CDN配置
if not DEBUG:
    # 生产环境使用本地静态文件路径
    STATIC_URL = '/static/'

# 静态文件压缩配置
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
]

COMPRESS_ENABLED = not DEBUG
COMPRESS_CSS_FILTERS = [
    'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.rCSSMinFilter',
]
COMPRESS_JS_FILTERS = [
    'compressor.filters.jsmin.JSMinFilter',
]
COMPRESS_STORAGE = 'compressor.storage.GzipCompressorFileStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# 日志配置 - 带轮转功能
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,                # 保留5个备份
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'error.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['error_file', 'console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'inventory': {  # 自定义应用日志
            'handlers': ['file', 'error_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 缓存配置（使用Redis缓存，性能更好）
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        }
    }
}

# 性能监控配置
SLOW_REQUEST_THRESHOLD = float(os.getenv('SLOW_REQUEST_THRESHOLD', '2.0'))  # 慢请求阈值（秒）

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# 登录限流配置
LOGIN_MAX_ATTEMPTS = int(os.getenv('LOGIN_MAX_ATTEMPTS', '5'))
LOGIN_LOCKOUT_SECONDS = int(os.getenv('LOGIN_LOCKOUT_SECONDS', '300'))

# 可信代理 IP 列表（仅来自这些 IP 的请求才信任 X-Forwarded-For 头）
# 生产环境部署时，应设置为反向代理（如 Nginx）的 IP 地址
# 例如：TRUSTED_PROXIES = ['127.0.0.1', '10.0.0.1']
TRUSTED_PROXIES = [
    ip.strip()
    for ip in os.getenv('TRUSTED_PROXIES', '').split(',')
    if ip.strip()
]

# 可信源列表，用于 CSRF 验证
CSRF_TRUSTED_ORIGINS = [
    'http://localhost',
    'https://localhost',
    'http://127.0.0.1',
    'https://127.0.0.1',
    'https://erp.sdyhjzgc.com',
    'http://erp.sdyhjzgc.com',
]

# ---------- 测试环境优化 ----------
# 使用快速密码哈希器，将每次 authenticate() 从 ~1s 降至 ~0.001s
TESTING = 'test' in sys.argv or 'pytest' in sys.modules
if TESTING:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    # 测试环境使用本地内存缓存，避免依赖数据库缓存表
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
    # 关闭调试日志减少 I/O 开销
    LOGGING['loggers']['django']['level'] = 'WARNING'
    LOGGING['loggers']['inventory']['level'] = 'WARNING'
    # 禁用 debug toolbar 中间件（测试中无需）
    MIDDLEWARE = [m for m in MIDDLEWARE if 'debug_toolbar' not in m]
    # 禁用模板调试，减少模板渲染开销
    for tmpl in TEMPLATES:
        tmpl['OPTIONS']['debug'] = False

# ---------- 生产环境安全配置 ----------
if not DEBUG and not TESTING:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

if not DEBUG:
    # 静态资源版本化：collectstatic 时为文件名追加内容 hash，
    # 避免部署更新后浏览器缓存导致用户看到旧版界面
    # 使用 ManifestStaticFilesStorage 进行版本化
    STORAGES = {
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
        },
    }

# ---------- REST Framework 配置 ----------
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ] if not DEBUG else [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
}

# ---------- Celery 配置 ----------
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30分钟超时
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25分钟软超时

# ---------- 环境覆盖（分层入口） ----------
# 通过 APP_ENV 选择附加覆盖模块：dev/prod/test
APP_ENV = os.getenv('APP_ENV', '').strip().lower()
if not APP_ENV:
    APP_ENV = 'prod' if not DEBUG else 'dev'

_ENV_MODULES = {
    'dev': 'minierp.settings_dev',
    'prod': 'minierp.settings_prod',
    'test': 'minierp.settings_test',
}
_module_path = _ENV_MODULES.get(APP_ENV)
if _module_path:
    try:
        import importlib

        _module = importlib.import_module(_module_path)
        _apply = getattr(_module, 'apply', None)
        if callable(_apply):
            _apply(globals())
    except Exception:
        # 覆盖模块异常不应阻断主配置加载，保留基础配置可用性
        pass
