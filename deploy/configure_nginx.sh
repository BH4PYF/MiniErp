#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}开始配置 Nginx 代理...${NC}"

# 复制配置文件
echo -e "${YELLOW}1. 复制 Nginx 配置文件...${NC}"
sudo cp /home/abc/MiniErp/deploy/minierp.conf /etc/nginx/sites-available/

# 创建符号链接
echo -e "${YELLOW}2. 创建符号链接...${NC}"
sudo ln -sf /etc/nginx/sites-available/minierp.conf /etc/nginx/sites-enabled/

# 检查 Nginx 配置
echo -e "${YELLOW}3. 检查 Nginx 配置...${NC}"
sudo nginx -t

if [ $? -eq 0 ]; then
    # 重启 Nginx
echo -e "${YELLOW}4. 重启 Nginx 服务...${NC}"
    sudo systemctl restart nginx
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Nginx 配置成功！${NC}"
        echo -e "${GREEN}系统已配置为使用 https://material.sdyhjzgc.com${NC}"
        echo -e "${GREEN}Gunicorn 服务器正在运行在 http://0.0.0.0:8000${NC}"
    else
        echo -e "${RED}✗ Nginx 重启失败${NC}"
    fi
else
    echo -e "${RED}✗ Nginx 配置检查失败${NC}"
fi

# 显示访问信息
echo -e "\n${GREEN}访问地址：${NC}"
echo -e "- HTTPS: https://material.sdyhjzgc.com"
echo -e "- HTTP: http://material.sdyhjzgc.com (会自动重定向到 HTTPS)"
echo -e "\n${YELLOW}注意：确保域名 material.sdyhjzgc.com 已正确解析到服务器 IP${NC}"
