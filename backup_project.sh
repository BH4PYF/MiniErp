#!/bin/bash

# 项目完整备份脚本
# 备份内容：数据库 + 项目文件 + 配置文件
# 支持本地备份和网络共享备份

set -e

# 配置
PROJECT_DIR="/home/abc/MiniErp"
DB_NAME="material_system"
BACKUP_DIR_LOCAL="/home/abc/project_backups"
BACKUP_DIR_NET="/mnt/network_backup"
NET_SHARE="//sdyh-bak.local/李善涛/软件/00000"
CREDENTIALS_FILE="/home/abc/.backup_credentials"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="material_project_${DATE}"
LOG_FILE="${PROJECT_DIR}/logs/project_backup.log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" >> "$LOG_FILE"
    case $level in
        INFO) echo -e "${GREEN}[INFO]${NC} ${message}" ;;
        WARN) echo -e "${YELLOW}[WARN]${NC} ${message}" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} ${message}" ;;
        STEP) echo -e "${BLUE}[STEP]${NC} ${message}" ;;
    esac
}

# 创建必要的目录
mkdir -p "$BACKUP_DIR_LOCAL"
sudo mkdir -p "$BACKUP_DIR_NET" 2>/dev/null || true
sudo chown $(id -u):$(id -g) "$BACKUP_DIR_NET" 2>/dev/null || true
mkdir -p "$(dirname "$LOG_FILE")"

# 创建临时备份目录
TEMP_BACKUP_DIR="/tmp/${BACKUP_NAME}"
mkdir -p "$TEMP_BACKUP_DIR"

log STEP "===================================="
log STEP "开始项目完整备份"
log STEP "===================================="

# 步骤1：备份数据库
log STEP "步骤 1/5: 备份数据库"
DB_BACKUP_FILE="${TEMP_BACKUP_DIR}/database.sql.gz"
if sudo -u postgres pg_dump "$DB_NAME" | gzip > "$DB_BACKUP_FILE"; then
    DB_SIZE=$(ls -lh "$DB_BACKUP_FILE" | awk '{print $5}')
    log INFO "数据库备份成功: $DB_SIZE"
else
    log ERROR "数据库备份失败！"
    rm -rf "$TEMP_BACKUP_DIR"
    exit 1
fi

# 步骤2：备份项目文件
log STEP "步骤 2/5: 备份项目文件"
PROJECT_BACKUP_DIR="${TEMP_BACKUP_DIR}/project"
mkdir -p "$PROJECT_BACKUP_DIR"

# 复制关键项目文件（排除不必要的文件）
rsync -av --progress \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.pyd' \
    --exclude='.git' \
    --exclude='.env' \
    --exclude='venv' \
    --exclude='env' \
    --exclude='node_modules' \
    --exclude='*.log' \
    --exclude='backups' \
    --exclude='db_backups' \
    --exclude='project_backups' \
    --exclude='*.pid' \
    --exclude='*.sock' \
    "$PROJECT_DIR/" "$PROJECT_BACKUP_DIR/"

log INFO "项目文件备份完成"

# 步骤3：备份配置文件
log STEP "步骤 3/5: 备份系统配置"
CONFIG_BACKUP_DIR="${TEMP_BACKUP_DIR}/configs"
mkdir -p "$CONFIG_BACKUP_DIR"

# 备份Nginx配置
if [ -f "/etc/nginx/conf.d/material-system.conf" ]; then
    sudo cp "/etc/nginx/conf.d/material-system.conf" "$CONFIG_BACKUP_DIR/"
    log INFO "Nginx配置已备份"
fi

# 备份Systemd服务配置
if [ -f "/etc/systemd/system/material-system.service" ]; then
    sudo cp "/etc/systemd/system/material-system.service" "$CONFIG_BACKUP_DIR/"
    log INFO "Systemd服务配置已备份"
fi

# 备份环境变量（如果有）
if [ -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env" "$CONFIG_BACKUP_DIR/dotenv"
    log INFO "环境变量配置已备份"
fi

# 备份crontab配置
crontab -l > "$CONFIG_BACKUP_DIR/crontab.txt" 2>/dev/null || true
log INFO "Crontab配置已备份"

# 步骤4：创建备份信息文件
log STEP "步骤 4/5: 创建备份信息"
cat > "${TEMP_BACKUP_DIR}/backup_info.txt" << EOF
项目备份信息
================
备份时间: $(date '+%Y-%m-%d %H:%M:%S')
备份名称: ${BACKUP_NAME}
服务器: $(hostname)
用户: $(whoami)
项目路径: ${PROJECT_DIR}
数据库: ${DB_NAME}

备份内容:
- 数据库备份 (database.sql.gz)
- 项目文件 (project/)
- 系统配置 (configs/)

恢复说明:
1. 解压备份文件
2. 恢复数据库: gunzip < database.sql.gz | psql -U postgres material_system
3. 恢复项目文件到原目录
4. 恢复配置文件
EOF

# 打包整个备份
log STEP "步骤 5/5: 打包备份文件"
cd /tmp
FINAL_BACKUP_FILE="${BACKUP_NAME}.tar.gz"
tar -czf "$FINAL_BACKUP_FILE" "$BACKUP_NAME"

# 移动到本地备份目录
mv "$FINAL_BACKUP_FILE" "$BACKUP_DIR_LOCAL/"
FINAL_SIZE=$(ls -lh "$BACKUP_DIR_LOCAL/$FINAL_BACKUP_FILE" | awk '{print $5}')
log INFO "本地备份完成: ${FINAL_BACKUP_FILE} (${FINAL_SIZE})"

# 清理临时目录
rm -rf "$TEMP_BACKUP_DIR"

# 尝试网络共享备份
log STEP "尝试网络共享备份"
if [ -f "$CREDENTIALS_FILE" ]; then
    if ! mountpoint -q "$BACKUP_DIR_NET"; then
        log INFO "正在挂载网络共享..."
        if sudo mount -t cifs "$NET_SHARE" "$BACKUP_DIR_NET" -o credentials="$CREDENTIALS_FILE",uid=$(id -u),gid=$(id -g),file_mode=0644,dir_mode=0755,vers=3.0 2>/dev/null; then
            log INFO "网络共享挂载成功"
        else
            log WARN "网络共享挂载失败，将仅保留本地备份"
        fi
    else
        log INFO "网络共享已挂载"
    fi
else
    log WARN "未找到凭证文件，跳过网络共享备份"
fi

# 复制到网络共享
if mountpoint -q "$BACKUP_DIR_NET"; then
    if cp "$BACKUP_DIR_LOCAL/$FINAL_BACKUP_FILE" "$BACKUP_DIR_NET/"; then
        NET_SIZE=$(ls -lh "$BACKUP_DIR_NET/$FINAL_BACKUP_FILE" 2>/dev/null | awk '{print $5}')
        log INFO "网络备份成功: $NET_SIZE"
    else
        log ERROR "复制到网络共享失败"
    fi
fi

# 清理旧备份
log STEP "清理旧备份文件"
# 本地保留7天
find "$BACKUP_DIR_LOCAL" -name "material_project_*.tar.gz" -type f -mtime +7 -delete
log INFO "已清理7天前的本地备份"

# 网络共享保留30天
if mountpoint -q "$BACKUP_DIR_NET"; then
    find "$BACKUP_DIR_NET" -name "material_project_*.tar.gz" -type f -mtime +30 -delete
    log INFO "已清理30天前的网络备份"
fi

# 统计信息
LOCAL_COUNT=$(find "$BACKUP_DIR_LOCAL" -name "material_project_*.tar.gz" | wc -l)
LOCAL_TOTAL=$(du -sh "$BACKUP_DIR_LOCAL" | cut -f1)

log STEP "===================================="
log STEP "备份任务完成"
log STEP "===================================="
log INFO "备份文件: ${FINAL_BACKUP_FILE}"
log INFO "文件大小: ${FINAL_SIZE}"
log INFO "本地备份数: ${LOCAL_COUNT} 个"
log INFO "本地总大小: ${LOCAL_TOTAL}"
log STEP "===================================="
