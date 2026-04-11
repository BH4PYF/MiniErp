#!/bin/bash
# 材料管理系统 - 生产环境测试启动脚本（HTTP）
# 用法：sudo bash start_production_test.sh

set -e  # 出错即停

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  材料管理系统生产环境测试启动（HTTP）${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then 
   echo -e "${RED}请以 root 权限运行此脚本：sudo bash start_production_test.sh${NC}" 
   exit 1
fi

# 获取当前用户名
REAL_USER=${SUDO_USER:-$USER}
HOME_DIR=$(eval echo ~$REAL_USER)
APP_DIR="$HOME_DIR/MiniErp"

echo -e "\n${GREEN}[1/5] 配置 Nginx HTTP...${NC}"
NGINX_CONF="/etc/nginx/sites-available/material-system-test.conf"

# 创建 Nginx 配置文件
cat > $NGINX_CONF << NGINX_EOF
# 材料管理系统测试配置
server {
    listen 8080;
    server_name localhost;
    
    client_max_body_size 20M;
    
    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        access_log off;
    }
    
    location /media/ {
        alias $APP_DIR/media/;
        expires 7d;
    }
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location /health/ {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
NGINX_EOF

# 启用 Nginx 配置
ln -sf /etc/nginx/sites-available/material-system-test.conf /etc/nginx/sites-enabled/

# 测试 Nginx 配置
echo -e "${YELLOW}测试 Nginx 配置...${NC}"
if nginx -t; then
    echo -e "${GREEN}✓ Nginx 配置测试通过${NC}"
else
    echo -e "${RED}✗ Nginx 配置测试失败${NC}"
    exit 1
fi

echo -e "\n${GREEN}[2/5] 准备 Django 环境...${NC}"
cd $APP_DIR

# 激活虚拟环境
source venv/bin/activate

# 收集静态文件
echo -e "${YELLOW}收集静态文件...${NC}"
python manage.py collectstatic --noinput
echo -e "${GREEN}✓ 静态文件收集完成${NC}"

# 数据库迁移
echo -e "${YELLOW}检查数据库迁移...${NC}"
python manage.py migrate --noinput
echo -e "${GREEN}✓ 数据库迁移完成${NC}"

echo -e "\n${GREEN}[3/5] 启动 Gunicorn 后台服务...${NC}"
# 停止现有的 Gunicorn 进程（如果有）
if pgrep -f "gunicorn.*material_system" > /dev/null; then
    echo -e "${YELLOW}停止现有的 Gunicorn 进程...${NC}"
    pkill -f "gunicorn.*material_system" || true
    sleep 2
fi

# 启动 Gunicorn
echo -e "${YELLOW}启动 Gunicorn...${NC}"
cd $APP_DIR
nohup gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --timeout 60 \
    --access-logfile logs/gunicorn_access.log \
    --error-logfile logs/gunicorn_error.log \
    --log-level info \
    --worker-class sync \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    material_system.wsgi:application > /dev/null 2>&1 &

GUNICORN_PID=$!
sleep 3

# 检查 Gunicorn 是否启动成功
if ps -p $GUNICORN_PID > /dev/null; then
    echo -e "${GREEN}✓ Gunicorn 已启动 (PID: $GUNICORN_PID)${NC}"
else
    echo -e "${RED}✗ Gunicorn 启动失败${NC}"
    exit 1
fi

echo -e "\n${GREEN}[4/5] 重启 Nginx...${NC}"
systemctl restart nginx
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Nginx 已重启${NC}"
else
    echo -e "${RED}✗ Nginx 启动失败${NC}"
    exit 1
fi

echo -e "\n${GREEN}[5/5] 验证服务...${NC}"
sleep 2

# 检查本地 HTTP 访问
echo -e "${YELLOW}测试 HTTP 连接...${NC}"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health/ | grep -q "200"; then
    echo -e "${GREEN}✓ HTTP 健康检查通过${NC}"
else
    echo -e "${YELLOW}⚠ HTTP 连接测试失败，请检查防火墙和配置${NC}"
fi

# 显示状态
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 生产环境测试启动完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\n访问地址:"
echo -e "  ${GREEN}http://localhost:8080${NC}"
echo -e "\n服务信息:"
echo -e "  Gunicorn PID: $GUNICORN_PID"
echo -e "  Gunicorn 监听：127.0.0.1:8000"
echo -e "  Nginx 监听：8080 (HTTP)"
echo -e "\n日志文件:"
echo -e "  Django 日志：$APP_DIR/logs/django.log"
echo -e "  Gunicorn 日志：$APP_DIR/logs/gunicorn_*.log"
echo -e "  Nginx 日志：/var/log/nginx/error.log"
echo -e "\n${YELLOW}常用命令：${NC}"
echo -e "  查看 Gunicorn 进程：ps aux | grep gunicorn"
echo -e "  停止 Gunicorn: pkill -f 'gunicorn.*material_system'"
echo -e "  重启 Nginx: sudo systemctl restart nginx"
echo -e "  查看 Nginx 状态：sudo systemctl status nginx"
echo -e "  实时日志：tail -f $APP_DIR/logs/django.log"
