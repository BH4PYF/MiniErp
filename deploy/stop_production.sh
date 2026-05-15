#!/bin/bash
# MiniErp 停止服务脚本
# 用法：bash deploy/stop_production.sh

set -e
GREEN='\033[0;32m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}停止 MiniErp 服务...${NC}"
cd "$PROJECT_DIR"
docker compose down
echo -e "${GREEN}服务已停止${NC}"
