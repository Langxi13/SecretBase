# Deployment Notes

This document describes a generic SecretBase deployment. Replace every placeholder with your own values.

## Recommended Layout

```text
/opt/secretbase/
├── backend/
├── frontend/
├── scripts/
└── venv/
```

The backend should run behind a reverse proxy and bind only to localhost:

```env
HOST=127.0.0.1
PORT=10004
CORS_ORIGINS=https://your-domain.example
```

## Basic Steps

1. Clone the repository to your server.
2. Create a Python virtual environment.
3. Install `backend/requirements.txt`.
4. Copy `backend/.env.example` to `backend/.env` and edit it.
5. Set restrictive permissions on `.env`, data, backup, and log directories.
6. Run the backend as a systemd service.
7. Serve `frontend/` through nginx or another static web server.
8. Proxy `/api/` to `http://127.0.0.1:10004`.
9. Enable HTTPS.
10. Add Basic Auth, VPN, or a zero-trust access layer before public exposure.

## Nginx Sketch

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.example;

    root /opt/secretbase/frontend;
    index index.html;

    location / {
        expires -1;
        add_header Cache-Control "no-cache, must-revalidate";
        try_files $uri $uri/ /index.html;
    }

    location = /secretbase-runtime-config.js {
        expires -1;
        add_header Cache-Control "no-store, no-cache, must-revalidate, max-age=0";
        try_files $uri =404;
    }

    location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg)$ {
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    location /api/ {
        rewrite ^/api/(.*) /$1 break;
        proxy_pass http://127.0.0.1:10004;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 10m;
    }

    location ~ ^/(backend|docs|scripts)/ {
        deny all;
    }
}
```

生产环境如果对 CSS/JS 使用长缓存，`frontend/index.html` 中的本地 CSS/JS 引用必须带版本查询参数，并在每次前端发布时递增。入口 HTML 应要求浏览器重新验证，`/secretbase-runtime-config.js` 是运行时配置脚本，应单独禁用缓存。

## Data Safety

- Never deploy local `backend/data/`, `backend/logs/`, or `backend/.env` from a development machine.
- Before restoring a backup, create a separate backup of the current vault.
- In-app automatic backups are stored under `BACKUP_DIR/auto/` and are rotated by the `auto_backup_retention` setting, default 30 and range 5-200. Manual backups are stored under `BACKUP_DIR/manual/` and are not removed by automatic rotation.
- Existing root-level `secretbase.enc.*.bak` files are migrated into `BACKUP_DIR/auto/` when backup management runs.
- Do not change vault format or migration behavior without an explicit backup and restore rehearsal.

## Health Checks

```bash
curl http://127.0.0.1:10004/health
systemctl status secretbase
nginx -t
```

Use `scripts/healthcheck.sh` as a starting point and adjust paths before installing it as a cron job or timer.
