#!/bin/bash
# 统一备份脚本
# 备份 MiniErp 项目和 www.sdyhjzgc.com 网站项目
# 用法: ./scripts/unified_backup.sh [保留天数]

set -e

# 配置
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups"
WEB_PROJECT_DIR="/home/abc/www.sdyhjzgc.com"
RETENTION_DAYS=${1:-30}  # 默认保留30天

# 从环境变量获取数据库配置
DB_NAME=${DB_NAME:-"material_system"}
DB_USER=${DB_USER:-"postgres"}
DB_PASSWORD=${DB_PASSWORD:-"postgres"}
DB_HOST=${DB_HOST:-"127.0.0.1"}
DB_PORT=${DB_PORT:-"5432"}

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 创建备份目录
mkdir -p "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR/websites"
mkdir -p "$BACKUP_DIR/databases"

# 生成时间戳
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")

# 备份 MiniErp 项目
echo -e "${YELLOW}================================${NC}"
echo -e "${GREEN}开始备份 MiniErp 项目...${NC}"
echo -e "${YELLOW}================================${NC}"

# 1. 备份 MiniErp 数据库
MINIERP_DB_BACKUP="$BACKUP_DIR/databases/minierp-$TIMESTAMP.sql"
echo -e "${GREEN}备份 MiniErp 数据库...${NC}"
PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$MINIERP_DB_BACKUP"
# 压缩备份
gzip -f "$MINIERP_DB_BACKUP"
MINIERP_DB_BACKUP_GZ="$MINIERP_DB_BACKUP.gz"
# 获取文件大小
FILESIZE=$(du -h "$MINIERP_DB_BACKUP_GZ" | cut -f1)
echo -e "${GREEN}✅ MiniErp 数据库备份成功: $MINIERP_DB_BACKUP_GZ ($FILESIZE)${NC}"

# 2. 备份 MiniErp 项目文件
MINIERP_FILES_BACKUP="$BACKUP_DIR/websites/minierp-$TIMESTAMP.tar.gz"
echo -e "${GREEN}备份 MiniErp 项目文件...${NC}"
tar -czf "$MINIERP_FILES_BACKUP" --exclude="venv" --exclude="backups" --exclude=".git" --exclude="*.pyc" --exclude="__pycache__" "$PROJECT_DIR"
# 获取文件大小
FILESIZE=$(du -h "$MINIERP_FILES_BACKUP" | cut -f1)
echo -e "${GREEN}✅ MiniErp 项目文件备份成功: $MINIERP_FILES_BACKUP ($FILESIZE)${NC}"

# 备份 www.sdyhjzgc.com 网站项目
echo -e "${YELLOW}================================${NC}"
echo -e "${GREEN}开始备份 www.sdyhjzgc.com 网站项目...${NC}"
echo -e "${YELLOW}================================${NC}"

# 1. 备份网站数据库（假设是MySQL）
WEB_DB_BACKUP="$BACKUP_DIR/databases/www_sdyhjzgc_com-$TIMESTAMP.sql"
echo -e "${GREEN}备份 www.sdyhjzgc.com 数据库...${NC}"
# 尝试使用MySQL备份
if command -v mysqldump &> /dev/null; then
    # 从网站配置文件读取数据库配置
    if [ -f "$WEB_PROJECT_DIR/application/database.php" ]; then
        # 提取数据库配置
        DB_CONFIG=$(grep -A 20 "'type'" "$WEB_PROJECT_DIR/application/database.php")
        WEB_DB_HOST=$(echo "$DB_CONFIG" | grep "'hostname'" | awk -F"'" '{print $4}')
        WEB_DB_USER=$(echo "$DB_CONFIG" | grep "'username'" | awk -F"'" '{print $4}')
        WEB_DB_PASS=$(echo "$DB_CONFIG" | grep "'password'" | awk -F"'" '{print $4}')
        WEB_DB_NAME=$(echo "$DB_CONFIG" | grep "'database'" | awk -F"'" '{print $4}')
        
        if [ -n "$WEB_DB_NAME" ]; then
            mysqldump -h "${WEB_DB_HOST:-localhost}" -u "${WEB_DB_USER:-root}" -p"${WEB_DB_PASS:-}" "$WEB_DB_NAME" > "$WEB_DB_BACKUP"
            # 压缩备份
            gzip -f "$WEB_DB_BACKUP"
            WEB_DB_BACKUP_GZ="$WEB_DB_BACKUP.gz"
            # 获取文件大小
            FILESIZE=$(du -h "$WEB_DB_BACKUP_GZ" | cut -f1)
            echo -e "${GREEN}✅ www.sdyhjzgc.com 数据库备份成功: $WEB_DB_BACKUP_GZ ($FILESIZE)${NC}"
        else
            echo -e "${YELLOW}⚠️  未找到网站数据库配置，跳过数据库备份${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  未找到数据库配置文件，跳过数据库备份${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  mysqldump 命令未找到，跳过数据库备份${NC}"
fi

# 2. 备份网站文件
WEB_FILES_BACKUP="$BACKUP_DIR/websites/www_sdyhjzgc_com-$TIMESTAMP.tar.gz"
echo -e "${GREEN}备份 www.sdyhjzgc.com 网站文件...${NC}"
tar -czf "$WEB_FILES_BACKUP" --exclude=".git" --exclude="uploads" --exclude="runtime" --exclude="data/session*" "$WEB_PROJECT_DIR"
# 获取文件大小
FILESIZE=$(du -h "$WEB_FILES_BACKUP" | cut -f1)
echo -e "${GREEN}✅ www.sdyhjzgc.com 网站文件备份成功: $WEB_FILES_BACKUP ($FILESIZE)${NC}"

# 清理旧备份
echo -e "${YELLOW}================================${NC}"
echo -e "${YELLOW}清理 $RETENTION_DAYS 天前的备份...${NC}"

# 清理数据库备份
find "$BACKUP_DIR/databases" -name "*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete

# 清理网站备份
find "$BACKUP_DIR/websites" -name "*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete

# 统计剩余备份
echo -e "${YELLOW}================================${NC}"
echo -e "${GREEN}📊 当前备份统计:${NC}"

# 统计数据库备份
DB_BACKUP_COUNT=$(find "$BACKUP_DIR/databases" -name "*.sql.gz" | wc -l)
DB_BACKUP_SIZE=$(du -sh "$BACKUP_DIR/databases" | cut -f1)
echo -e "${GREEN}数据库备份: $DB_BACKUP_COUNT 个, 总大小: $DB_BACKUP_SIZE${NC}"

# 统计网站备份
WEB_BACKUP_COUNT=$(find "$BACKUP_DIR/websites" -name "*.tar.gz" | wc -l)
WEB_BACKUP_SIZE=$(du -sh "$BACKUP_DIR/websites" | cut -f1)
echo -e "${GREEN}网站备份: $WEB_BACKUP_COUNT 个, 总大小: $WEB_BACKUP_SIZE${NC}"

# 总备份大小
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo -e "${GREEN}总备份大小: $TOTAL_SIZE${NC}"

# 显示最近的备份
echo -e "${YELLOW}================================${NC}"
echo -e "${GREEN}最近的备份文件:${NC}"
find "$BACKUP_DIR" -type f -name "*$TIMESTAMP*" | sort

# 网络同步（同步到SMB网络存储）
NETWORK_BACKUP_DIR="/mnt/sdyh_nas/ERP/minierp_backups"

if mountpoint -q /mnt/sdyh_nas 2>/dev/null; then
    echo -e "${YELLOW}================================${NC}"
    echo -e "${GREEN}开始同步到网络存储 (SMB)...${NC}"
    
    # 确保网络备份目录存在
    sudo mkdir -p "$NETWORK_BACKUP_DIR"
    
    # 同步数据库备份到网络存储
    sudo rsync -av "$BACKUP_DIR/databases/" "$NETWORK_BACKUP_DIR/"
    
    # 同步网站备份到网络存储
    sudo rsync -av "$BACKUP_DIR/websites/" "$NETWORK_BACKUP_DIR/"
    
    echo -e "${GREEN}✅ 网络存储同步成功！${NC}"
else
    echo -e "${YELLOW}⚠️  网络存储未挂载，跳过网络同步${NC}"
    echo -e "${YELLOW}⚠️  请先挂载SMB共享: sudo mount -t cifs //sdyh-nas.local/李善涛/软件/00000 /mnt/sdyh_nas -o credentials=/home/abc/.smb_credentials${NC}"
fi

echo -e "${YELLOW}================================${NC}"
echo -e "${GREEN}✅ 统一备份完成！${NC}"
echo -e "${YELLOW}================================${NC}"
