#!/bin/bash
# 材料管理系统 - 停止生产环境服务

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  停止材料管理系统生产环境服务${NC}"
echo -e "${GREEN}========================================${NC}"

# 停止 Gunicorn
echo -e "${YELLOW}正在停止 Gunicorn...${NC}"
if pgrep -f "gunicorn.*material_system" > /dev/null; then
    pkill -f "gunicorn.*material_system"
    echo -e "${GREEN}✓ Gunicorn 已停止${NC}"
else
    echo -e "${YELLOW}⚠ Gunicorn 未运行${NC}"
fi

# 停止 Nginx（可选）
read -p "是否也要停止 Nginx 服务？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}正在停止 Nginx...${NC}"
    systemctl stop nginx
    echo -e "${GREEN}✓ Nginx 已停止${NC}"
fi

echo -e "\n${GREEN}服务已停止${NC}"
