# MiniErp 项目管理系统 V2.0

[![Django](https://img.shields.io/badge/Django-6.0.3-green)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

专业的工程项目全流程管理系统，集成材料管理、分包管理、合同管理、进度计量、结算管理等核心功能，为工程项目提供一站式解决方案。

## 功能特性

### 项目管理模块
- **项目管理**：项目信息管理、项目预算跟踪、成本统计、状态跟踪
- **合同管理**：合同档案管理、合同清单维护、合同状态跟踪
- **分包商管理**：分包商信息维护、分包商用户管理、信用评级
- **分包清单管理**：分包清单分类、清单明细管理、参数配置

### 进度计量与结算
- **进度计量**：进度计量创建、计量清单填报、产值自动计算、累计产值统计
- **分包结算**：分包结算创建、计量产值汇总、扣款管理、最终结算计算
- **Excel 导出**：进度计量列表、计量详情、结算列表、结算详情导出

### 材料管理模块
- **材料管理**：材料档案管理、分类管理、重复名称校验
- **材料计划**：材料需求计划、计划明细管理
- **采购计划**：采购计划制定、审批流程、状态跟踪、批量导出
- **发货管理**：发货单创建、物流跟踪、批量导出
- **快速收货**：极简收货流程、自动填充信息
- **入库管理**：材料入库登记、Excel 导出、批次管理

### 统计分析
- **仪表盘**：项目成本概览、关键指标展示
- **统计报表**：项目成本分析、供应商采购排名、月度统计
- **图表分析**：入库总额 TOP10 柱状图、入库大类分布饼图，支持日期范围筛选
- **操作日志**：完整的审计日志、操作追踪
- **Excel 导出**：各类业务数据导出功能

### 系统管理
- **用户管理**：多角色权限控制（管理员/管理层/供应商/分包商）
- **系统设置**：导航栏标题定制、材料分类管理、登录限流配置
- **权限控制**：基于角色的访问控制
- **数据备份**：定时自动备份、手动备份支持
- **性能监控**：API 性能统计、慢请求追踪

## 快速开始

### 环境要求
- Docker & Docker Compose
- Git (可选)

### 安装步骤（Docker）

#### 1. 获取项目
```bash
git clone https://github.com/BH4PYF/MiniErp.git
cd MiniErp
```

#### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件修改配置（特别是 SECRET_KEY 和数据库密码）
```

#### 3. 启动服务
```bash
docker compose up -d
```

#### 4. 初始化数据库
```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser  # 创建管理员账号
```

访问 http://127.0.0.1:6666/

服务包含：
- **web**: Django 应用（Gunicorn）
- **db**: PostgreSQL 16
- **redis**: Redis 7
- **celery**: Celery 异步任务 Worker

## 浏览器支持

- Chrome (推荐)
- Firefox
- Safari
- Edge

## 部署到生产环境

部署使用 Docker Compose + Nginx + HTTPS 方案。详细步骤见 `deploy/DEPLOYMENT_HTTPS.md`。

```bash
# 快速参考
sudo cp deploy/minierp.conf /etc/nginx/conf.d/
sudo systemctl restart nginx
docker compose up -d
```

## 项目结构

```
MiniErp/
├── deploy/                     # 部署脚本目录
│   ├── start_production_https.sh   # 生产环境一键启动
│   ├── start_production_test.sh    # 测试环境启动
│   ├── stop_production.sh          # 停止生产服务
│   ├── configure_nginx.sh          # Nginx 配置
│   ├── minierp.conf                # Nginx 站点配置
│   ├── minierp.service             # systemd 服务文件
│   ├── gunicorn_config.py          # Gunicorn 配置
│   └── DEPLOYMENT_HTTPS.md         # 部署详细文档
├── inventory/                  # 主应用
│   ├── api/                   # API 接口
│   ├── management/commands/   # 自定义管理命令
│   ├── migrations/            # 数据库迁移
│   ├── services/              # 业务服务层
│   ├── templatetags/          # 模板标签
│   ├── views/                 # 视图函数（按功能模块拆分）
│   │   ├── auth.py            # 登录/登出
│   │   ├── dashboard.py       # 仪表盘
│   │   ├── budget.py          # 预算管理
│   │   ├── contract.py        # 合同管理
│   │   ├── measurement.py     # 进度计量
│   │   ├── settlement.py      # 分包结算
│   │   ├── delivery.py        # 发货管理
│   │   ├── export.py          # Excel 导入导出
│   │   ├── inbound.py         # 入库管理
│   │   ├── material.py        # 材料管理
│   │   ├── material_plan.py   # 材料计划
│   │   ├── performance.py     # 性能监控
│   │   ├── project.py         # 项目管理
│   │   ├── purchase_plan.py   # 采购计划
│   │   ├── report.py          # 统计报表与图表分析
│   │   ├── settings.py        # 系统设置
│   │   ├── supplier.py        # 供应商管理
│   │   ├── subcontractor.py   # 分包商管理
│   │   ├── subcontract_list.py# 分包清单管理
│   │   └── utils.py           # 工具函数
│   ├── models.py              # 数据模型（含软删除基础设施）
│   ├── urls.py                # URL 路由
│   ├── admin.py               # Admin 配置
│   ├── context_processors.py  # 上下文处理器
│   └── tests/                 # 单元测试
├── minierp/                   # Django 项目配置
│   ├── settings.py            # 基础配置
│   ├── settings_dev.py        # 开发环境配置
│   ├── settings_prod.py       # 生产环境配置
│   ├── settings_test.py       # 测试环境配置
│   ├── urls.py                # 根路由
│   ├── wsgi.py                # WSGI 配置
│   ├── asgi.py                # ASGI 配置
│   ├── celery.py              # Celery 配置
│   └── middleware.py          # 中间件配置
├── scripts/                   # 工具脚本
│   ├── backup_db.sh           # 数据库备份脚本
│   ├── setup_cron_backup.sh   # 定时备份配置
│   └── reset_database.sh      # 数据库重置脚本
├── static/                    # 静态文件
│   ├── css/                   # 样式文件
│   ├── js/                    # JavaScript 文件
│   └── vendor/                # 第三方库（Bootstrap 等）
├── templates/                 # HTML 模板
│   ├── base.html              # 基础模板
│   ├── login.html             # 登录页面
│   └── inventory/             # 业务模块模板
├── logs/                      # 日志文件
├── .env.example               # 环境变量示例
├── manage.py                  # Django 管理脚本
├── requirements.txt           # Python 依赖
├── pytest.ini                 # Pytest 配置
└── conftest.py                # Pytest 配置
```

## 数据库备份

### 定时备份设置（推荐）

```bash
# 一键设置定时备份（交互式）
bash scripts/setup_cron_backup.sh

# 或手动配置 crontab
crontab -e
# 添加：每天凌晨 2 点自动备份
0 2 * * * cd /path/to/MiniErp && bash scripts/backup_db.sh 30 >> logs/backup.log 2>&1
```

### 手动备份

```bash
# 手动触发备份
bash scripts/backup_db.sh [保留天数]
```

备份文件保存在 `backups/` 目录，自动压缩，默认保留 30 天。

## 主要功能模块

### 1. 仪表盘
- 项目成本概览
- 关键业务指标展示
- 今日入库记录

### 2. 项目管理
- 项目信息维护、状态跟踪（进行中/已完工/暂停）
- 项目预算管理
- 项目成本统计
- 支持 Excel 导入导出

### 3. 预算管理
- 项目预算编制
- 预算执行跟踪
- 预算分析报表

### 4. 合同管理
- 合同档案管理
- 合同清单维护
- 合同状态跟踪
- 支持 Excel 导入导出

### 5. 分包商管理
- 分包商信息维护、信用评级
- 分包商用户管理
- 支持 Excel 导入导出

### 6. 分包清单管理
- 分包清单分类管理
- 清单明细维护
- 施工参数配置

### 7. 进度计量
- 进度计量创建、计量清单填报
- 本期产值、累计产值自动计算
- 支持 Excel 导出

### 8. 分包结算
- 分包结算创建、计量产值汇总
- 扣款管理、最终结算计算
- 支持 Excel 导出

### 9. 材料管理
- 材料档案维护、材料分类管理
- 支持 Excel 导入导出

### 10. 材料计划
- 材料需求计划编制
- 计划明细管理
- 支持 Excel 导入导出

### 11. 供应商管理
- 供应商信息维护、信用评级（优秀/良好/一般）
- 采购记录查询
- 支持 Excel 导入导出

### 12. 采购计划
- 采购计划制定、状态跟踪（审批中/采购中/发货中/已入库）
- 批量导入导出、预计金额计算

### 13. 发货管理
- 发货单创建、物流跟踪（专车/物流）
- 车牌号/运单号记录
- 批量导入导出

### 14. 快速收货
- 极简收货流程、自动填充信息

### 15. 入库管理
- 入库登记、质量验收、批次管理
- 支持 Excel 导入导出

### 16. 统计报表
- 项目成本分析、供应商采购排名、月度统计报表

### 17. 图表分析
- 入库总额 TOP10 柱状图
- 入库大类分布饼图
- 支持日期范围筛选

### 18. 系统管理
- 用户管理、角色权限配置
- 系统设置（导航栏标题、登录限流）
- 材料分类管理（自定义分类、重复名称校验）
- 数据备份与恢复、操作日志查询
- 性能监控仪表盘

## 安全配置

生产环境部署前必须修改：

1. **生成新密钥**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
   将输出粘贴到 `.env` 的 `SECRET_KEY`

2. **关闭调试模式**
   在 `.env` 中设置 `DEBUG=False`

3. **限制允许的主机**
   在 `.env` 中设置 `ALLOWED_HOSTS=你的域名或IP`

## 日志

日志文件位于 `logs/django.log`，记录系统运行信息和错误。

## 测试

```bash
# 运行所有测试
python manage.py test inventory

# 或使用 pytest（需要先安装）
pytest

# 带覆盖率报告
pytest --cov=inventory --cov-report=html
```

## 更新日志

### v2.1.1 (2026-05-12)
- **安全加固**：硬编码密码替换为随机生成、9 处异常处理规范化
- **Bug 修复**：serializer 移除不存在字段、dashboard 状态筛选修复、材料计划导出 Q 对象修复
- **API 完善**：22 个模型 ViewSet/Serializer/FilterSet 全覆盖
- **数据库优化**：8 个模型添加 11 个索引、SubcontractList.category 改为外键
- **角色精简**：移除 material_dept 和 clerk 角色，简化为 4 个角色（admin/management/supplier/subcontractor）
- **部署统一**：端口统一为 7777、新增移动端 (`/m/`)

### v2.1.0 (2026-05-01)
- **Docker 化部署**：docker compose 一键启动（PostgreSQL + Redis + Celery）
- **基础设施升级**：Django 6.0 + PostgreSQL 替代 SQLite/MySQL
- **登录限流**：Redis 缓存，5次/300秒
- **慢请求监控**：>2s 记录到 deque 缓存
- **生产安全**：HSTS/SSL/Cookie Secure/Sentry 集成

### v2.0 (2026-04-11)
- **重大升级**：从材料管理系统升级为项目管理系统（MiniErp）
- **新增模块**：预算管理、合同管理、分包商管理、分包清单管理、进度计量、分包结算
- **新增功能**：材料计划管理
- **功能优化**：用户角色扩展（新增分包商、管理层角色）
- **代码优化**：修复进度计量和结算编号生成逻辑
- **文档更新**：全面更新 README 文档

### v1.10 (2026-03-31)
- 修复用户编辑成功提示从横幅改成模态框的问题
- 修改编辑模态框中的角色分组选择
- 清理无用的文件和代码
- 优化项目目录结构

### v1.9 (2026-03-26)
- 图表分析页面优化
- 系统设置页面操作提示统一为模态框
- 材料分类删除改用模态框确认
- 材料分类添加增加重复名称校验
- 修复软删除记录导致分类编码冲突的问题

---

## 贡献

欢迎提交 Issue 或 Pull Request。

## 许可证

[MIT License](LICENSE)

## 联系方式

项目维护者：妞妞爸
