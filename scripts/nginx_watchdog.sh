#!/bin/bash
# Nginx 看门狗 — 每分钟检查一次，如果挂了就拉起
# crontab: * * * * * /bin/bash /home/abc/MiniErp/scripts/nginx_watchdog.sh

LOG_FILE="/home/abc/MiniErp/deploy/logs/nginx_watchdog.log"
MAX_LOG_SIZE=$((10 * 1024 * 1024))  # 10MB 轮转

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

rotate_log() {
    if [ -f "$LOG_FILE" ] && [ "$(stat -c%s "$LOG_FILE" 2>/dev/null)" -gt "$MAX_LOG_SIZE" ]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
    fi
}

rotate_log

if systemctl is-active --quiet nginx; then
    exit 0
fi

log "NGINX_DOWN: nginx 服务未运行，尝试重启..."
systemctl start nginx 2>&1 | while read -r line; do log "  $line"; done
sleep 2

if systemctl is-active --quiet nginx; then
    log "NGINX_RECOVERED: nginx 重启成功"
else
    log "NGINX_FAILED: nginx 重启失败！请检查 systemctl status nginx"
fi
