# MiniErp 生产环境部署指南

## 系统要求

- Ubuntu 20.04/22.04/24.04
- Docker + Docker Compose
- Nginx（宿主机安装，反向代理）
- SSL 证书（acme.sh 自动管理）
- 域名：`your-domain.com`

## 部署架构

```
用户 → Nginx (:80/:443) → Gunicorn (:6666, Docker 容器)
                              ↓
                         PostgreSQL (:5432, Docker 容器)
                              Redis (:6379, Docker 容器)
                              Celery (Docker 容器)
```

## 部署步骤

### 1. 准备环境

```bash
git clone https://github.com/BH4PYF/MiniErp.git ~/MiniErp
cd ~/MiniErp
cp .env.example .env
# 编辑 .env，配置 SECRET_KEY、ALLOWED_HOSTS 等
```

### 2. 配置 Nginx

```bash
sudo cp deploy/minierp.conf /etc/nginx/conf.d/
sudo nginx -t
sudo systemctl restart nginx
```

### 3. 启动 Docker 服务

```bash
docker compose up -d
```

服务列表：

| 容器 | 端口 | 说明 |
|------|------|------|
| `minierp-web` | 6666 | Gunicorn + Django |
| `minierp-celery` | — | 异步任务 Worker |
| `postgres-db` | 5432 | PostgreSQL 数据库 |
| `redis-db` | 6379 | Redis 缓存 + 消息队列 |

### 4. 初始化数据库

```bash
docker exec minierp-web python manage.py migrate
docker exec minierp-web python manage.py createsuperuser
```

### 5. 配置 SSL 证书

```bash
acme.sh --issue -d your-domain.com --nginx
acme.sh --install-cert -d your-domain.com \
    --cert-file /path/to/cert --key-file /path/to/key
```

### 6. 验证

```bash
curl https://your-domain.com/health/    # → "healthy"
docker ps                                 # 查看容器状态
```

## 常用命令

### 管理服务

```bash
docker compose up -d              # 启动
docker compose down               # 停止
docker compose restart web celery # 重启
docker ps                         # 查看状态
docker logs -f minierp-web        # 查看日志
```

### 更新部署

```bash
cd ~/MiniErp
git pull
docker compose build web celery
docker compose up -d web celery
```

### 数据库备份

```bash
bash scripts/backup_db.sh       # 仅数据库（每夜 2:00 自动）
bash scripts/backup_files.sh    # 仅文件（每夜 3:00 自动）
```

## 健康检查

| 端点 | 方式 |
|------|------|
| Nginx `/health/` | 直接返回 "healthy" |
| Gunicorn `:6666/health/` | Python urllib（Docker healthcheck） |
| Celery | `celery inspect ping` |

## 安全配置

- HSTS / SSL 重定向 / Cookie Secure
- `/health/` 豁免 SSL 重定向
- 系统 PostgreSQL / Redis 已禁用自启（防端口冲突）
- 登录限流：5次/300秒

## 端口冲突预防

```bash
sudo systemctl disable --now postgresql redis-server minierp 2>/dev/null
sudo systemctl mask postgresql
```

## Nginx 看门狗

每分钟检查 Nginx 运行状态，异常时自动拉起。脚本已内置日志轮转（10MB）。

```bash
# 手动安装（部署时执行一次）
chmod +x scripts/nginx_watchdog.sh
(crontab -l 2>/dev/null; echo '* * * * * /home/abc/MiniErp/scripts/nginx_watchdog.sh') | crontab -
```

三重保护：
- `systemd Restart=always` — 进程崩溃 5 秒内自动重启
- cron 看门狗 — 被手动停止 / 启动失败时每分钟拉起
- `systemctl enable nginx` — 服务器重启后自动启动

| 日志 | 路径 |
|------|------|
| 看门狗 | `deploy/logs/nginx_watchdog.log` |

## 日志位置

| 日志 | 路径 |
|------|------|
| Gunicorn | `deploy/logs/gunicorn_*.log` |
| Nginx | `/var/log/nginx/` |
| Docker stdout | `docker logs minierp-web` |

## 相关文件

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | Docker 编排 |
| `Dockerfile` | 镜像构建 |
| `deploy/minierp.conf` | Nginx 配置 |
| `deploy/gunicorn_config.py` | Gunicorn 配置 |
| `scripts/backup_db.sh` | 数据库备份 |
| `scripts/backup_files.sh` | 文件备份 |
| `scripts/nginx_watchdog.sh` | Nginx 看门狗 |

---

**最后更新**: 2026-05-15
**版本**: 2.1.0
