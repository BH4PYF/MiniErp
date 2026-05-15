#!/bin/bash
# MiniErp 生产环境启动脚本
# 用法：sudo bash deploy/start_production_https.sh

set -e
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  MiniErp 生产环境启动${NC}"
echo -e "${GREEN}========================================${NC}"

cd "$PROJECT_DIR"

# 1. 配置 Nginx
echo -e "\n${GREEN}[1/3] 配置 Nginx...${NC}"
sudo cp "$SCRIPT_DIR/minierp.conf" /etc/nginx/conf.d/minierp.conf
if sudo nginx -t 2>/dev/null; then
    sudo systemctl restart nginx
    echo -e "${GREEN}Nginx 配置完成${NC}"
else
    echo -e "${YELLOW}Nginx 配置检查失败，请先编辑 deploy/minierp.conf${NC}"
fi

# 2. 启动 Docker 服务
echo -e "\n${GREEN}[2/3] 启动 Docker 服务...${NC}"
docker compose up -d

# 3. 等待并验证
echo -e "\n${GREEN}[3/3] 验证服务...${NC}"
sleep 5
docker ps --format "table {{.Names}}\t{{.Status}}"
echo ""
curl -s -o /dev/null -w "健康检查: HTTP %{http_code}\n" http://localhost:6666/health/

echo -e "\n${GREEN}启动完成${NC}"
