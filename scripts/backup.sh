#!/bin/bash
# backup.sh - 手动备份脚本

set -e

APP_DIR="${APP_DIR:-/opt/secretbase}"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/secretbase}"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 备份数据文件
if [ -f "$APP_DIR/backend/data/secretbase.enc" ]; then
    cp "$APP_DIR/backend/data/secretbase.enc" "$BACKUP_DIR/secretbase.enc.$DATE"
    echo "备份数据文件: secretbase.enc.$DATE"
fi

# 备份配置文件。该文件可能包含密钥，请保护 BACKUP_DIR 权限。
if [ -f "$APP_DIR/backend/.env" ]; then
    cp "$APP_DIR/backend/.env" "$BACKUP_DIR/env.$DATE"
    echo "备份配置文件: env.$DATE"
fi

# 备份设置文件，兼容旧版根目录路径和新版 data/ 路径。
for SETTINGS_FILE in "$APP_DIR/backend/data/settings.json" "$APP_DIR/backend/settings.json"; do
    if [ -f "$SETTINGS_FILE" ]; then
        cp "$SETTINGS_FILE" "$BACKUP_DIR/settings.json.$DATE"
        echo "备份设置文件: settings.json.$DATE"
        break
    fi
done

# 清理 30 天前的备份
find "$BACKUP_DIR" -type f -mtime +30 -delete 2>/dev/null || true

echo "备份完成: $BACKUP_DIR"
