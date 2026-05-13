#!/bin/bash
# 数据库备份脚本（Docker 版）
# 用法: ./scripts/backup_db.sh [保留天数]

set -e

# 配置
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups"
RETENTION_DAYS=${1:-30}  # 默认保留30天
CONTAINER_NAME="postgres-db"

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

# 执行备份（通过 docker exec，无需密码）
docker exec "$CONTAINER_NAME" pg_dump -U postgres material_system > "$BACKUP_FILE"

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
