# MiniErp 项目管理系统

## 项目概览

施工企业项目全流程管理系统 V2.0，Django 6.0 + PostgreSQL + Redis + Celery，部署在 erp.sdyhjzgc.com (Gunicorn:7777 + Nginx)。

**业务模块**: 项目管理 → 合同管理 → 分包管理 → 进度计量 → 分包结算 → 材料管理(计划/采购/发货/入库) → 统计分析 → 系统管理

**用户角色**: admin(管理员) / management(管理层) / supplier(供应商) / subcontractor(分包商)

## 技术架构

- 软删除基类 `SoftDeleteModel`（is_deleted + deleted_at），所有业务模型继承
- 自定义密码验证：12位 + 大小写 + 数字 + 特殊字符
- 登录限流：Redis 缓存，5次/300秒
- REST API：DRF ViewSet，22 个模型全覆盖，FilterSet + Search + Ordering
- 角色权限装饰器：`admin_management_required`（utils.py），限制供应商/分包商写入
- 生产安全：HSTS/SSL/Cookie Secure/Sentry/ManifestStaticFilesStorage
- 慢请求监控：>2s 记录到 deque 缓存（最近100条）
- Excel 导入导出：openpyxl
- 移动端：`/m/` 和 `/m/report/`

## 开发约定

- **简单实用优先**，不过度设计，不引入不必要的抽象
- 视图用 Django 原生函数视图 + 装饰器，不做 SPA 改造
- 错误处理用 `(IntegrityError, DatabaseError)`，不用裸 `except Exception`
- 供应商/分包商密码用 `secrets.token_urlsafe()` 随机生成，不硬编码
- 中文注释和变量名可接受
- API 新增模型按现有模式：FilterSet → ViewSet → Serializer → Router 注册

## 关键文件

| 文件 | 职责 |
|------|------|
| `inventory/models.py` | 全部数据模型 + 软删除基础设施 |
| `inventory/views/*.py` | 业务视图（按模块拆分） |
| `inventory/api/` | REST API（views.py + serializers.py + urls.py） |
| `inventory/services/` | 业务服务层 |
| `minierp/settings.py` | 基础配置（自动加载 settings_dev/prod/test 覆盖） |
| `minierp/middleware.py` | 性能分析 + 慢请求监控 |
| `deploy/` | 部署脚本（gunicorn_config.py + nginx conf + systemd） |
| `templates/` | Django 模板（含 mobile/ 移动端） |
| `静态文件` | static/（开发）+ staticfiles/（生产 collectstatic） |

## 已完成的改进 (2026-05-12)

### Bug 修复
- serializer 移除不存在的 `location` 字段（ProjectSerializer, InboundRecordSerializer）
- dashboard 状态筛选 `pending` → `planning`
- material_plan 导出 Q 对象 Bug 修复

### 安全加固
- 硬编码密码 → `secrets.token_urlsafe(8)` 随机生成
- ROLE_CHOICES 补全 4 个角色
- 6 个视图模块加 `admin_management_required` 权限校验
- 9 处 `except Exception` → `except (IntegrityError, DatabaseError)`

### 基础设施
- 8 个模型 11 个数据库索引 + migration 0039
- InboundRecord 加 `location` 字段 + migration 0040
- SubcontractList.category CharField → FK(SubcontractCategory) + migration 0041
- 部署端口统一 6666 → 7777

### API 层
- 22 个模型全覆盖（原 6 个 + 新 16 个 ViewSet/Serializer/FilterSet/路由）

### 其他
- Mobile 模板 + 视图 + 路由 (`/m/`)
- README 部署文档修复
- 4 个孤儿模板删除
- 残留文件 `=5.9.0` 清理 + .gitignore
