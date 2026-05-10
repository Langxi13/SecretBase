#!/bin/bash
# restore.sh - 恢复备份脚本

set -e

if [ -z "$1" ]; then
    echo "用法: $0 <备份文件路径>"
    echo "示例: APP_DIR=/opt/secretbase $0 /path/to/encrypted-vault-backup"
    exit 1
fi

BACKUP_FILE="$1"
APP_DIR="${APP_DIR:-/opt/secretbase}"
APP_USER="${APP_USER:-vault}"
APP_NAME="${APP_NAME:-secretbase}"

# 检查备份文件
if [ ! -f "$BACKUP_FILE" ]; then
    echo "备份文件不存在: $BACKUP_FILE"
    exit 1
fi

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "请使用 root 权限运行此脚本"
    exit 1
fi

# 停止服务
echo "停止服务..."
systemctl stop "$APP_NAME"

# 备份当前数据
echo "备份当前数据..."
BACKUP_CURRENT="$APP_DIR/backend/data/secretbase.enc.backup.$(date +%Y%m%d_%H%M%S)"
if [ -f "$APP_DIR/backend/data/secretbase.enc" ]; then
    cp "$APP_DIR/backend/data/secretbase.enc" "$BACKUP_CURRENT"
fi

# 恢复数据
echo "恢复数据..."
cp "$BACKUP_FILE" "$APP_DIR/backend/data/secretbase.enc"
chown "$APP_USER:$APP_USER" "$APP_DIR/backend/data/secretbase.enc"
chmod 600 "$APP_DIR/backend/data/secretbase.enc"

# 启动服务
echo "启动服务..."
systemctl start "$APP_NAME"

echo "恢复完成"
if [ -f "$BACKUP_CURRENT" ]; then
    echo "原数据已备份至: $BACKUP_CURRENT"
fi
