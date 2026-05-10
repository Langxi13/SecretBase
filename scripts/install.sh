#!/bin/bash
set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration. Override these when needed:
#   APP_DIR=/opt/secretbase APP_USER=vault ./scripts/install.sh
APP_NAME="${APP_NAME:-secretbase}"
APP_USER="${APP_USER:-vault}"
APP_DIR="${APP_DIR:-/opt/secretbase}"

echo -e "${GREEN}=== SecretBase 安装脚本 ===${NC}"
echo -e "${YELLOW}应用目录: $APP_DIR${NC}"
echo -e "${YELLOW}运行用户: $APP_USER${NC}"

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 权限运行此脚本${NC}"
    exit 1
fi

# 更新系统包
echo -e "${YELLOW}更新系统包...${NC}"
apt update
apt upgrade -y

# 安装依赖
echo -e "${YELLOW}安装系统依赖...${NC}"
apt install -y python3 python3-pip python3-venv nginx

# 创建应用用户
echo -e "${YELLOW}创建应用用户...${NC}"
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -s /bin/false -d "$APP_DIR" "$APP_USER"
    echo -e "${GREEN}用户 $APP_USER 创建成功${NC}"
else
    echo -e "${YELLOW}用户 $APP_USER 已存在${NC}"
fi

# 创建目录结构
echo -e "${YELLOW}创建目录结构...${NC}"
mkdir -p "$APP_DIR"/{backend/data/backups,backend/logs}

if [ ! -f "$APP_DIR/backend/requirements.txt" ]; then
    echo -e "${RED}未找到 $APP_DIR/backend/requirements.txt。请先将仓库克隆或复制到 APP_DIR。${NC}"
    exit 1
fi

# 创建 Python 虚拟环境
echo -e "${YELLOW}创建 Python 虚拟环境...${NC}"
python3 -m venv "$APP_DIR/venv"
source "$APP_DIR/venv/bin/activate"

# 安装 Python 依赖
echo -e "${YELLOW}安装 Python 依赖...${NC}"
pip install --upgrade pip
pip install -r "$APP_DIR/backend/requirements.txt"

# 创建 .env 文件
echo -e "${YELLOW}创建配置文件...${NC}"
if [ ! -f "$APP_DIR/backend/.env" ]; then
    cp "$APP_DIR/backend/.env.example" "$APP_DIR/backend/.env"
    echo -e "${GREEN}配置文件创建成功${NC}"
else
    echo -e "${YELLOW}配置文件已存在，跳过${NC}"
fi

# 设置文件权限
echo -e "${YELLOW}设置文件权限...${NC}"
chmod 600 "$APP_DIR/backend/.env"
chmod 700 "$APP_DIR/backend/data"
chmod 700 "$APP_DIR/backend/data/backups"
chmod 700 "$APP_DIR/backend/logs"
chown -R "$APP_USER:$APP_USER" "$APP_DIR/backend/data" "$APP_DIR/backend/logs"

# 安装 systemd 服务
echo -e "${YELLOW}安装 systemd 服务...${NC}"
cat > /etc/systemd/system/$APP_NAME.service << EOF
[Unit]
Description=SecretBase Password Manager
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR/backend
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/python main.py
Restart=always
RestartSec=5

# 安全加固
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP_DIR/backend/data $APP_DIR/backend/logs
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$APP_NAME"
echo -e "${GREEN}systemd 服务安装成功${NC}"

# 配置 nginx
echo -e "${YELLOW}配置 nginx...${NC}"
cat > /etc/nginx/sites-available/$APP_NAME << EOF
server {
    listen 80;
    server_name _;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # 前端静态文件
    root $APP_DIR/frontend;
    index index.html;

    # 前端路由
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # API 代理
    location /api/ {
        rewrite ^/api/(.*) /\$1 break;
        proxy_pass http://127.0.0.1:10004;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 请求大小限制
        client_max_body_size 10m;
    }

    # 静态资源缓存
    location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg)$ {
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # 禁止访问隐藏文件
    location ~ /\. {
        deny all;
    }
}
EOF

ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

nginx -t && systemctl reload nginx
echo -e "${GREEN}nginx 配置成功${NC}"

# 启动服务
echo -e "${YELLOW}启动服务...${NC}"
systemctl start "$APP_NAME"

echo -e "${GREEN}=== 安装完成 ===${NC}"
echo -e "${GREEN}访问你的 nginx 域名或 http://localhost 开始使用${NC}"
echo ""
echo -e "${YELLOW}常用命令：${NC}"
echo -e "  查看状态: systemctl status $APP_NAME"
echo -e "  查看日志: journalctl -u $APP_NAME -f"
echo -e "  重启服务: systemctl restart $APP_NAME"
echo -e "  停止服务: systemctl stop $APP_NAME"
