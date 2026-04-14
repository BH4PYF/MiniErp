#!/bin/bash
# 数据库备份脚本
# 用法: ./scripts/backup_db.sh [保留天数]

set -e

# 配置
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups"
RETENTION_DAYS=${1:-30}  # 默认保留30天

# 从环境变量获取数据库配置
DB_NAME=${DB_NAME:-"material_system"}
DB_USER=${DB_USER:-"postgres"}
DB_PASSWORD=${DB_PASSWORD:-""}
DB_HOST=${DB_HOST:-"127.0.0.1"}
DB_PORT=${DB_PORT:-"5432"}

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 生成备份文件名 (格式: db-YYYYMMDD-HHMMSS.sql)
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BACKUP_FILE="$BACKUP_DIR/db-$TIMESTAMP.sql"

# 执行备份
PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$BACKUP_FILE"

# 压缩备份
gzip -f "$BACKUP_FILE"
BACKUP_FILE_GZ="$BACKUP_FILE.gz"

# 获取文件大小
FILESIZE=$(du -h "$BACKUP_FILE_GZ" | cut -f1)

echo -e "${GREEN}✅ 备份成功: $BACKUP_FILE_GZ ($FILESIZE)${NC}"

# 清理旧备份
echo -e "${YELLOW}清理 $RETENTION_DAYS 天前的备份...${NC}"
find "$BACKUP_DIR" -name "db-*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete

# 统计剩余备份
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "db-*.sql.gz" | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

echo -e "${GREEN}📊 当前备份: $BACKUP_COUNT 个, 总大小: $TOTAL_SIZE${NC}"

echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}备份完成！${NC}"
echo -e "${GREEN}================================${NC}"
