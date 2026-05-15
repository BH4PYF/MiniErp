#!/bin/bash
# MiniErp 测试环境启动脚本（HTTP，无 HTTPS）
# 用法：bash deploy/start_production_test.sh

set -e
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo -e "${GREEN}启动 MiniErp 测试环境...${NC}"

# 如果 .env 中 DEBUG 未设置，临时启用
docker compose up -d

sleep 3
echo ""
docker ps --format "table {{.Names}}\t{{.Status}}"
echo ""
curl -s -o /dev/null -w "健康检查: HTTP %{http_code}\n" http://localhost:6666/health/
echo -e "${GREEN}测试环境启动完成，访问 http://localhost:6666${NC}"
