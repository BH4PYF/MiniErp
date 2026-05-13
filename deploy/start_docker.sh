#!/bin/bash
# MiniErp Docker 生产环境启动脚本
# 首次运行或容器被删除后重建全部服务

set -e

# PostgreSQL
docker rm -f postgres-db 2>/dev/null || true
docker run -d --name postgres-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=material_system \
  -v pgdata:/var/lib/postgresql/data \
  -p 127.0.0.1:5432:5432 \
  --restart unless-stopped \
  registry.cn-hangzhou.aliyuncs.com/jeecgdocker/pgvector:latest

# Redis
docker rm -f redis-db 2>/dev/null || true
docker run -d --name redis-db \
  -v redis-data:/data \
  -p 127.0.0.1:6379:6379 \
  --restart unless-stopped \
  registry.cn-hangzhou.aliyuncs.com/jeecgdocker/redis:5.0 \
  redis-server --appendonly yes --save 900 1 --save 300 10 --save 60 10000

# Wait for DB and Redis
sleep 3

# Web (Gunicorn)
docker rm -f minierp-web 2>/dev/null || true
docker run -d --name minierp-web \
  --network host \
  --env-file /home/abc/MiniErp/.env \
  -e REDIS_HOST=localhost \
  -e REDIS_PORT=6379 \
  -e DB_HOST=127.0.0.1 \
  -e DB_PORT=5432 \
  -v /home/abc/MiniErp/staticfiles:/app/staticfiles \
  -v /home/abc/MiniErp/media:/app/media \
  -v /home/abc/MiniErp/deploy/logs:/app/deploy/logs \
  --restart unless-stopped \
  minierp:latest

# Celery Worker
docker rm -f minierp-celery 2>/dev/null || true
docker run -d --name minierp-celery \
  --network host \
  --env-file /home/abc/MiniErp/.env \
  -e REDIS_HOST=localhost \
  -e REDIS_PORT=6379 \
  -e DB_HOST=127.0.0.1 \
  -e DB_PORT=5432 \
  -v /home/abc/MiniErp/staticfiles:/app/staticfiles \
  -v /home/abc/MiniErp/media:/app/media \
  -v /home/abc/MiniErp/deploy/logs:/app/deploy/logs \
  --restart unless-stopped \
  minierp:latest \
  celery -A minierp worker -l info -c 2

echo "All containers started."
docker ps --format 'table {{.Names}}\t{{.Status}}'
