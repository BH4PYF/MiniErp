#!/bin/bash
# MiniErp 项目文件备份脚本
# 仅备份项目文件（不含数据库）
# 用法: ./scripts/backup_files.sh [保留天数]

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups/files"
RETENTION_DAYS=${1:-30}

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BACKUP_FILE="$BACKUP_DIR/files-$TIMESTAMP.tar.gz"

echo -e "${YELLOW}================================${NC}"
echo -e "${GREEN}备份 MiniErp 项目文件...${NC}"
echo -e "${YELLOW}================================${NC}"

tar -czf "$BACKUP_FILE" \
    --exclude="venv" \
    --exclude="backups" \
    --exclude=".git" \
    --exclude="*.pyc" \
    --exclude="__pycache__" \
    --exclude="staticfiles" \
    --exclude="media" \
    --exclude="deploy/logs" \
    "$PROJECT_DIR"

FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo -e "${GREEN}文件备份成功: $BACKUP_FILE ($FILESIZE)${NC}"

echo -e "${YELLOW}清理 ${RETENTION_DAYS} 天前的文件备份...${NC}"
find "$BACKUP_DIR" -name "files-*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete

COUNT=$(find "$BACKUP_DIR" -name "files-*.tar.gz" | wc -l)
TOTAL=$(du -sh "$BACKUP_DIR" | cut -f1)
echo -e "${GREEN}当前: ${COUNT} 个, 总计: ${TOTAL}${NC}"

NET_DIR="/mnt/sdyh_nas/ERP/minierp_backups"
if mountpoint -q /mnt/sdyh_nas 2>/dev/null; then
    sudo mkdir -p "$NET_DIR"
    sudo rsync -av "$BACKUP_DIR/" "$NET_DIR/"
    echo -e "${GREEN}网络同步完成${NC}"
fi

echo -e "${GREEN}文件备份完成！${NC}"
