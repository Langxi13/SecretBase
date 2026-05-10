#!/bin/bash
# healthcheck.sh - 健康检查脚本

APP_NAME="${APP_NAME:-secretbase}"
APP_DIR="${APP_DIR:-/opt/secretbase}"
PORT="${PORT:-10004}"

# 检查服务状态
if ! systemctl is-active --quiet "$APP_NAME"; then
    echo "$(date): ERROR - SecretBase 服务未运行"
    systemctl start "$APP_NAME"
fi

# 检查 API 响应
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" 2>/dev/null)
if [ "$HTTP_CODE" != "200" ]; then
    echo "$(date): ERROR - API 健康检查失败 (HTTP $HTTP_CODE)"
    systemctl restart "$APP_NAME"
fi

# 检查磁盘空间
DISK_USAGE=$(df -h "$APP_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 90 ]; then
    echo "$(date): WARNING - 磁盘使用率超过 90%"
fi

# 检查日志文件大小
LOG_SIZE=$(du -sm "$APP_DIR/backend/logs/" 2>/dev/null | cut -f1)
LOG_SIZE="${LOG_SIZE:-0}"
if [ "$LOG_SIZE" -gt 1000 ]; then
    echo "$(date): WARNING - 日志文件超过 1GB"
fi
