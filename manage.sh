#!/bin/bash
# MiniErp 管理脚本
# 用法: ./manage.sh <command>

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

COMPOSE_FILE="docker-compose.yml"
BACKUP_SCRIPT="scripts/backup_db.sh"

case "${1:-help}" in
    up)
        echo -e "${GREEN}🚀 启动所有服务...${NC}"
        docker-compose -f "$COMPOSE_FILE" up -d
        echo -e "${GREEN}✅ 已启动${NC}"
        docker ps --format 'table {{.Names}}\t{{.Status}}'
        ;;
    down)
        echo -e "${YELLOW}🛑 停止所有服务...${NC}"
        docker-compose -f "$COMPOSE_FILE" down
        echo -e "${GREEN}✅ 已停止${NC}"
        ;;
    restart)
        echo -e "${YELLOW}🔄 重启所有服务...${NC}"
        docker-compose -f "$COMPOSE_FILE" restart
        echo -e "${GREEN}✅ 已重启${NC}"
        docker ps --format 'table {{.Names}}\t{{.Status}}'
        ;;
    logs)
        shift
        docker-compose -f "$COMPOSE_FILE" logs --tail=50 -f "$@"
        ;;
    web)
        docker-compose -f "$COMPOSE_FILE" logs --tail=50 -f web
        ;;
    celery)
        docker-compose -f "$COMPOSE_FILE" logs --tail=50 -f celery
        ;;
    db)
        docker-compose -f "$COMPOSE_FILE" logs --tail=50 -f db
        ;;
    redis)
        docker-compose -f "$COMPOSE_FILE" logs --tail=50 -f redis
        ;;
    bash)
        shift
        docker exec -it minierp-web bash
        ;;
    dbsh)
        docker exec -it postgres-db psql -U postgres material_system
        ;;
    backup)
        bash "$BACKUP_SCRIPT"
        ;;
    rebuild)
        echo -e "${YELLOW}🔨 重建镜像并启动...${NC}"
        docker-compose -f "$COMPOSE_FILE" build
        docker-compose -f "$COMPOSE_FILE" up -d
        echo -e "${GREEN}✅ 重建完成${NC}"
        docker ps --format 'table {{.Names}}\t{{.Status}}'
        ;;
    ps)
        docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
        ;;
    status)
        echo -e "${GREEN}📊 容器状态${NC}"
        docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
        echo ""
        echo -e "${GREEN}📦 镜像大小${NC}"
        docker images minierp --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'
        echo ""
        echo -e "${GREEN}💾 磁盘占用${NC}"
        echo -n "备份: "; du -sh backups/ 2>/dev/null || echo "无"
        echo -n "日志: "; du -sh deploy/logs/ 2>/dev/null || echo "无"
        ;;
    prune)
        echo -e "${YELLOW}🧹 清理旧镜像和未使用的资源...${NC}"
        docker image prune -f
        echo -e "${GREEN}✅ 清理完成${NC}"
        ;;
    help|*)
        echo -e "${GREEN}MiniErp 管理脚本${NC}"
        echo ""
        echo "用法: ./manage.sh <command>"
        echo ""
        echo "常用命令:"
        echo "  up        启动所有服务"
        echo "  down      停止所有服务"
        echo "  restart   重启所有服务"
        echo "  rebuild   重建镜像并启动"
        echo "  status    查看状态"
        echo "  ps        查看容器列表"
        echo "  logs      查看日志 (./manage.sh logs web)"
        echo "  web       查看 web 日志"
        echo "  celery    查看 celery 日志"
        echo "  db        查看数据库日志"
        echo "  backup    手动备份数据库"
        echo "  bash      进入 web 容器"
        echo "  dbsh      进入 PostgreSQL 命令行"
        echo "  prune     清理旧镜像"
        ;;
esac
