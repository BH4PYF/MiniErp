#!/bin/bash
# MiniErp Nginx 配置脚本
# 用法：sudo bash deploy/configure_nginx.sh

set -e
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}配置 Nginx 反向代理...${NC}"

# 复制配置文件
echo -e "${YELLOW}1. 复制 Nginx 配置...${NC}"
sudo cp "$SCRIPT_DIR/minierp.conf" /etc/nginx/conf.d/

# 检查配置
echo -e "${YELLOW}2. 检查 Nginx 配置...${NC}"
if sudo nginx -t; then
    echo -e "${YELLOW}3. 重启 Nginx...${NC}"
    sudo systemctl restart nginx
    echo -e "${GREEN}Nginx 配置完成${NC}"
else
    echo -e "${RED}Nginx 配置检查失败，请先修改 deploy/minierp.conf 中的域名和证书路径${NC}"
    exit 1
fi
