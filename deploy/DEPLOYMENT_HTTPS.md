# 生产环境部署指南 - HTTPS + Nginx

## 📋 系统要求

- Ubuntu 20.04/22.04/24.04
- Python 3.8+
- Nginx 1.18+
- SSL 证书（已准备好）
- 域名：`material.sdyhjzgc.com`

## 🔧 部署步骤

### 1. 准备 SSL 证书

确保您已有以下证书文件：
- 证书文件：`.crt` 或 `.pem` 格式
- 私钥文件：`.key` 格式

示例位置：
```
/etc/nginx/ssl/material.sdyhjzgc.com.crt
/etc/nginx/ssl/material.sdyhjzgc.com.key
```

### 2. 配置环境变量

编辑 `.env` 文件，确保以下配置正确：

```bash
# Django 环境变量配置 - 生产环境

# 安全密钥（生产环境专用）
SECRET_KEY=your_secure_secret_key_here

# 调试模式（生产环境必须设为 False）
DEBUG=False

# 允许的主机（生产环境必须指定具体域名）
ALLOWED_HOSTS=material.sdyhjzgc.com,www.material.sdyhjzgc.com,127.0.0.1,localhost

# 环境模式
APP_ENV=prod

# 数据库配置（PostgreSQL）
DB_NAME=material_system
DB_USER=postgres
DB_PASSWORD=your_db_password
DB_HOST=127.0.0.1
DB_PORT=5432

# 时区和语言
TIME_ZONE=Asia/Shanghai
LANGUAGE_CODE=zh-hans

# 可信代理 IP（Nginx）
TRUSTED_PROXIES=127.0.0.1

# 慢请求阈值（秒）
SLOW_REQUEST_THRESHOLD=2.0
```

### 3. 启动生产环境（自动配置 HTTPS）

使用自动化脚本启动：

```bash
sudo bash start_production_https.sh
```

脚本会自动完成以下操作：
1. ✅ 验证 SSL 证书
2. ✅ 配置 Nginx HTTPS
3. ✅ 收集 Django 静态文件
4. ✅ 启动 Gunicorn 后台服务
5. ✅ 重启 Nginx
6. ✅ 验证服务运行状态

### 4. 访问系统

启动成功后，可以通过以下地址访问：
- **HTTPS**: https://material.sdyhjzgc.com
- **HTTP**: http://material.sdyhjzgc.com（会自动跳转到 HTTPS）

## 🔒 HTTPS 强制跳转

系统已配置 HTTP 到 HTTPS 的自动跳转：
- 所有 HTTP 请求（80 端口）会自动 301 重定向到 HTTPS（443 端口）
- HSTS 头已启用，浏览器会强制使用 HTTPS

## 🛡️ 安全特性

### Nginx 安全配置
- ✅ TLS 1.2 和 TLS 1.3
- ✅ 强加密套件
- ✅ HSTS（严格传输安全）
- ✅ X-Frame-Options（防点击劫持）
- ✅ X-XSS-Protection
- ✅ X-Content-Type-Options
- ✅ Content-Security-Policy

### Django 安全配置
- ✅ DEBUG=False
- ✅ ALLOWED_HOSTS 限制
- ✅ CSRF 保护
- ✅ SQL 注入防护
- ✅ XSS 防护

## 📝 常用命令

### 查看服务状态
```bash
# 查看 Gunicorn 进程
ps aux | grep gunicorn

# 查看 Nginx 状态
sudo systemctl status nginx

# 查看 Gunicorn 系统服务状态（如已安装）
sudo systemctl status material-system
```

### 重启服务
```bash
# 重启 Gunicorn（如果使用 systemd）
sudo systemctl restart material-system

# 重启 Nginx
sudo systemctl restart nginx

# 手动重启 Gunicorn
pkill -f "gunicorn.*material_system"
sudo bash start_production_https.sh
```

### 查看日志
```bash
# Django 应用日志
tail -f /home/abc/Project-Material-Management-System/logs/django.log

# Gunicorn 日志
tail -f /home/abc/Project-Material-Management-System/logs/gunicorn_access.log
tail -f /home/abc/Project-Material-Management-System/logs/gunicorn_error.log

# Nginx 日志
sudo tail -f /var/log/nginx/material-system-access.log
sudo tail -f /var/log/nginx/material-system-error.log
```

### 停止服务
```bash
sudo bash stop_production.sh
```

## 🔍 故障排查

### 1. HTTPS 无法访问

**检查 SSL 证书路径：**
```bash
ls -la /etc/nginx/ssl/
```

**验证证书有效性：**
```bash
openssl x509 -in /etc/nginx/ssl/material.sdyhjzgc.com.crt -text -noout
```

**测试 Nginx 配置：**
```bash
sudo nginx -t
```

### 2. Gunicorn 未启动

**检查端口占用：**
```bash
netstat -tlnp | grep 8000
```

**手动启动 Gunicorn：**
```bash
cd /home/abc/Project-Material-Management-System
source venv/bin/activate
gunicorn --workers 3 --bind 127.0.0.1:8000 material_system.wsgi:application
```

### 3. 权限问题

**修复文件权限：**
```bash
sudo chown -R abc:abc /home/abc/Project-Material-Management-System
sudo chmod -R 755 /home/abc/Project-Material-Management-System/staticfiles
sudo chmod -R 755 /home/abc/Project-Material-Management-System/media
```

### 4. 防火墙配置

**开放必要端口：**
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw status
```

## 📊 性能优化建议

### 1. Gunicorn 优化
根据服务器配置调整 worker 数量：
```bash
# workers = (CPU 核心数 × 2) + 1
--workers 3
```

### 2. Nginx 优化
调整缓冲区和超时设置（已在配置文件中设置）

### 3. 数据库优化
- 添加数据库连接池
- 配置查询缓存
- 定期清理旧数据

### 4. 静态资源优化
- 启用 CDN
- 配置浏览器缓存
- 压缩 CSS/JS

## 🔄 更新部署

### 代码更新后
```bash
cd /home/abc/Project-Material-Management-System
git pull  # 或复制新代码

source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput

# 重启 Gunicorn
sudo systemctl restart material-system
# 或
pkill -f "gunicorn.*material_system"
sudo bash start_production_https.sh
```

## 📞 技术支持

如遇到问题，请检查：
1. 应用日志：`logs/django.log`
2. Web 服务器日志：`/var/log/nginx/`
3. 系统日志：`journalctl -u nginx`

## 📄 相关文件

- `start_production_https.sh` - HTTPS 启动脚本
- `stop_production.sh` - 停止服务脚本
- `deploy/nginx_https.conf` - Nginx HTTPS 配置模板
- `material-system.service` - systemd 服务配置
- `.env` - 环境变量配置

---

**最后更新**: 2026-03-30  
**版本**: 1.0.0
