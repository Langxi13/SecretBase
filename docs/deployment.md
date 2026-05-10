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
        try_files $uri $uri/ /index.html;
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

## Data Safety

- Never deploy local `backend/data/`, `backend/logs/`, or `backend/.env` from a development machine.
- Before restoring a backup, create a separate backup of the current vault.
- Do not change vault format or migration behavior without an explicit backup and restore rehearsal.

## Health Checks

```bash
curl http://127.0.0.1:10004/health
systemctl status secretbase
nginx -t
```

Use `scripts/healthcheck.sh` as a starting point and adjust paths before installing it as a cron job or timer.
