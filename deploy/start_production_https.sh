#!/bin/bash
# 项目管理系统 - 生产环境启动脚本（HTTPS + Nginx）
# 用法：sudo bash start_production_https.sh

set -e  # 出错即停

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  项目管理系统生产环境启动（HTTPS）${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then 
   echo -e "${RED}请以 root 权限运行此脚本：sudo bash start_production_https.sh${NC}" 
   exit 1
fi

# 获取当前用户名
REAL_USER=${SUDO_USER:-$USER}
HOME_DIR=$(eval echo ~$REAL_USER)
APP_DIR="$HOME_DIR/MiniErp"

echo -e "\n${GREEN}[1/6] 检查 SSL 证书...${NC}"
SSL_DIR="/etc/nginx/ssl"
CERT_FILE="/home/abc/.acme.sh/erp.sdyhjzgc.com_ecc/fullchain.cer"
KEY_FILE="/home/abc/.acme.sh/erp.sdyhjzgc.com_ecc/erp.sdyhjzgc.com.key"

# 使用指定的证书目录
echo -e "${YELLOW}使用指定的证书目录：/home/abc/.acme.sh/erp.sdyhjzgc.com_ecc${NC}"

if [ -z "$CERT_FILE" ] || [ ! -f "$CERT_FILE" ]; then
    echo -e "${RED}错误：证书文件不存在或无效：$CERT_FILE${NC}"
    exit 1
fi

if [ -z "$KEY_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo -e "${RED}错误：私钥文件不存在或无效：$KEY_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 证书文件验证通过${NC}"
echo -e "  证书：$CERT_FILE"
echo -e "  私钥：$KEY_FILE"

# 创建 SSL 目录并复制证书
mkdir -p $SSL_DIR
cp "$CERT_FILE" "$SSL_DIR/erp.sdyhjzgc.com_fullchain.crt"
cp "$KEY_FILE" "$SSL_DIR/erp.sdyhjzgc.com.key"
chmod 600 "$SSL_DIR/erp.sdyhjzgc.com.key"
chmod 644 "$SSL_DIR/erp.sdyhjzgc.com_fullchain.crt"
chown -R root:root $SSL_DIR
echo -e "${GREEN}✓ 证书已复制到 $SSL_DIR${NC}"

echo -e "\n${GREEN}[2/6] 配置 Nginx HTTPS...${NC}"
NGINX_CONF="/etc/nginx/sites-available/material-system-https.conf"

# 更新 Nginx 配置文件中的证书路径
cat > $NGINX_CONF << NGINX_EOF
# HTTP 到 HTTPS 重定向
server {
    listen 80;
    server_name erp.sdyhjzgc.com www.erp.sdyhjzgc.com;
    return 301 https://erp.sdyhjzgc.com$request_uri;
}

# HTTPS 服务器配置
server {
    listen 443 ssl http2;
    server_name erp.sdyhjzgc.com www.erp.sdyhjzgc.com;
    
    # 使用完整证书链（包含根证书和中级证书）
    ssl_certificate $SSL_DIR/erp.sdyhjzgc.com_fullchain.crt;
    ssl_certificate_key $SSL_DIR/erp.sdyhjzgc.com.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    
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
        proxy_pass http://127.0.0.1:6666;
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
ln -sf /etc/nginx/sites-available/material-system-https.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 测试 Nginx 配置
echo -e "${YELLOW}测试 Nginx 配置...${NC}"
if nginx -t; then
    echo -e "${GREEN}✓ Nginx 配置测试通过${NC}"
else
    echo -e "${RED}✗ Nginx 配置测试失败${NC}"
    exit 1
fi

echo -e "\n${GREEN}[3/6] 准备 Django 环境...${NC}"
cd $APP_DIR

# 激活虚拟环境
source venv/bin/activate

# 收集静态文件
echo -e "${YELLOW}收集静态文件...${NC}"

# 确保 STATIC_ROOT 目录存在且为空
STATIC_ROOT="$APP_DIR/staticfiles"
mkdir -p "$STATIC_ROOT"
rm -rf "$STATIC_ROOT"/*

# 运行 collectstatic 命令
python3 manage.py collectstatic --noinput
echo -e "${GREEN}✓ 静态文件收集完成${NC}"

# 数据库迁移
echo -e "${YELLOW}检查数据库迁移...${NC}"
python3 manage.py migrate --noinput
echo -e "${GREEN}✓ 数据库迁移完成${NC}"

echo -e "\n${GREEN}[4/6] 启动 Gunicorn 后台服务...${NC}"
# 停止现有的 Gunicorn 进程（如果有）
if pgrep -f "gunicorn.*minierp" > /dev/null; then
    echo -e "${YELLOW}停止现有的 Gunicorn 进程...${NC}"
    pkill -f "gunicorn.*minierp" || true
    sleep 2
fi

# 启动 Gunicorn
echo -e "${YELLOW}启动 Gunicorn...${NC}"
cd $APP_DIR
nohup gunicorn \
    --workers 3 \
    --bind 127.0.0.1:6666 \
    --timeout 60 \
    --access-logfile logs/gunicorn_access.log \
    --error-logfile logs/gunicorn_error.log \
    --log-level info \
    --worker-class sync \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    minierp.wsgi:application > /dev/null 2>&1 &

GUNICORN_PID=$!
sleep 3

# 检查 Gunicorn 是否启动成功
if ps -p $GUNICORN_PID > /dev/null; then
    echo -e "${GREEN}✓ Gunicorn 已启动 (PID: $GUNICORN_PID)${NC}"
else
    echo -e "${RED}✗ Gunicorn 启动失败${NC}"
    exit 1
fi

echo -e "\n${GREEN}[5/6] 重启 Nginx...${NC}"
systemctl restart nginx
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Nginx 已重启${NC}"
else
    echo -e "${RED}✗ Nginx 启动失败${NC}"
    exit 1
fi

echo -e "\n${GREEN}[6/6] 验证服务...${NC}"
sleep 2

# 检查本地 HTTPS 访问
echo -e "${YELLOW}测试 HTTPS 连接...${NC}"
if curl -k -s -o /dev/null -w "%{http_code}" https://localhost/health/ | grep -q "200"; then
    echo -e "${GREEN}✓ HTTPS 健康检查通过${NC}"
else
    echo -e "${YELLOW}⚠ HTTPS 连接测试失败，请检查防火墙和证书配置${NC}"
fi

# 显示状态
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ 生产环境启动完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "
访问地址:"
echo -e "  ${GREEN}https://erp.sdyhjzgc.com${NC}"
echo -e "  ${GREEN}https://www.erp.sdyhjzgc.com${NC}"
echo -e "
HTTP 将自动跳转到 HTTPS"
echo -e "\n服务信息:"
echo -e "  Gunicorn PID: $GUNICORN_PID"
echo -e "  Gunicorn 监听：127.0.0.1:8000"
echo -e "  Nginx 监听：80 (HTTP), 443 (HTTPS)"
echo -e "\n日志文件:"
echo -e "  Django 日志：$APP_DIR/logs/django.log"
echo -e "  Gunicorn 日志：$APP_DIR/logs/gunicorn_*.log"
echo -e "  Nginx 日志：/var/log/nginx/material-system-*.log"
echo -e "\n${YELLOW}常用命令：${NC}"
echo -e "  查看 Gunicorn 进程：ps aux | grep gunicorn"
echo -e "  停止 Gunicorn: pkill -f 'gunicorn.*material_system'"
echo -e "  重启 Nginx: sudo systemctl restart nginx"
echo -e "  查看 Nginx 状态：sudo systemctl status nginx"
echo -e "  实时日志：tail -f $APP_DIR/logs/django.log"
echo -e "\n${YELLOW}安全提示：${NC}"
echo -e "  ✓ 已强制使用 HTTPS"
echo -e "  ✓ HTTP 请求将自动跳转到 HTTPS"
echo -e "  ✓ 确保防火墙仅开放 80 和 443 端口"
