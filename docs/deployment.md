# Deployment Notes

This document describes a generic SecretBase deployment. Replace every placeholder with your own values.

## Local Source Startup

For a local single-user deployment, use the desktop foundation bootstrap instead of configuring nginx:

```text
Windows: start-secretbase.cmd
Linux/macOS: ./scripts/start-local.sh
```

The first run creates `.venv/`, installs pinned dependencies, allocates a random loopback port, and opens the application. Local data is stored outside the repository in the current user's application-data directory. Use `--data-root PATH` (or `-DataRoot PATH` in PowerShell) to override it.

## Windows Independent Desktop Package

V3.1 provides a PyInstaller one-folder Windows package with an independent pywebview/Edge WebView2 window. The package does not require a Python installation at runtime. It stores user data under `%LOCALAPPDATA%\SecretBase\` and keeps the source bootstrap above available for development and fallback use.

Build with Windows Python 3.11 x64:

```powershell
.\scripts\build-desktop-windows.ps1
```

The build writes `SecretBase-v3.1.0-windows-x64.zip` and `SHA256SUMS.txt` under `artifacts/`. It also runs a packaged backend/frontend self-test and rejects release directories containing `.env`, vault, backup, log, settings, test, documentation, or Git metadata files.

The target machine must have the Microsoft Edge WebView2 Runtime. Windows 10/11 normally includes it; when unavailable, SecretBase shows a startup error with the official runtime download option. Do not move files out of the extracted `SecretBase/` directory because `SecretBase.exe` depends on its `_internal/` contents.

Formal release assets are built on Windows Server 2022 and retested from the downloaded ZIP on Windows Server 2025. A release tag must match `backend/version.py` before GitHub Release uploads the ZIP and checksum.

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

    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    location / {
        expires -1;
        try_files $uri $uri/ /index.html;
    }

    location = /secretbase-runtime-config.js {
        expires -1;
        try_files $uri =404;
    }

    location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg)$ {
        expires 7d;
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

    location ~ ^/api/ai/(parse|organize/preview|tags/preview)$ {
        rewrite ^/api/(.*) /$1 break;
        proxy_pass http://127.0.0.1:10004;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
        client_max_body_size 10m;
    }

    location ~ ^/(backend|docs|scripts)/ {
        deny all;
    }
}
```

生产环境如果对 CSS/JS 使用长缓存，`frontend/index.html` 中的本地 CSS/JS 引用必须带版本查询参数，并在每次前端发布时递增。`expires` 指令不会打断服务器级安全头的继承；不要在静态资源 location 中单独添加 `add_header` 后遗漏安全头。入口 HTML 和 `/secretbase-runtime-config.js` 应要求浏览器重新验证。

## Data Safety

- Never deploy local `backend/data/`, `backend/logs/`, or `backend/.env` from a development machine.
- Keep `SETTINGS_PATH` inside the writable data directory. Deployments upgrading from an older `SETTINGS_PATH=./settings.json` should stop the service, move that file to `backend/data/settings.json`, preserve its contents and ownership, update `.env`, and then restart. This prevents atomic settings writes from failing when the application code directory is read-only.
- Before restoring a backup, create a separate backup of the current vault.
- In-app automatic backups are stored under `BACKUP_DIR/auto/` and are rotated by the `auto_backup_retention` setting, default 30 and range 5-200. Manual backups are stored under `BACKUP_DIR/manual/` and are not removed by automatic rotation.
- Existing root-level `secretbase.enc.*.bak` files are migrated into `BACKUP_DIR/auto/` when backup management runs.
- Do not change vault format or migration behavior without an explicit backup and restore rehearsal.
- The frontend runtime is vendored. Production and desktop startup do not need to execute JavaScript from a third-party CDN.

## Health Checks

```bash
curl http://127.0.0.1:10004/health
systemctl status secretbase
nginx -t
```

Use `scripts/healthcheck.sh` as a starting point and adjust paths before installing it as a cron job or timer.
