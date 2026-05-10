# SecretBase

SecretBase is a single-user encrypted password vault built with FastAPI and a Vue 3 CDN frontend. It stores data in one local encrypted vault file, with no database required.

## Features

- AES-256-GCM encrypted vault file using a master password.
- Single-user unlock/lock flow with session tokens.
- Entries with custom fields, tags, search, filters, sorting, trash, and backups.
- Import/export for encrypted backups and plain JSON.
- Optional AI-assisted parsing via DeepSeek-compatible chat completions API.
- Lightweight frontend: Vue 3 CDN, plain JavaScript, and CSS.
- Production-friendly deployment behind nginx with optional Basic Auth.

## Security Notes

- Do not commit `backend/.env`, `backend/data/`, `backend/logs/`, or any vault backup.
- The master password cannot be recovered if lost.
- Keep encrypted backups, and test restore flows before relying on them.
- For public deployments, bind the backend to `127.0.0.1` and put nginx or another reverse proxy in front of it.
- Basic Auth, VPN, or a zero-trust gateway is recommended before exposing the UI publicly.

## Local Development

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python main.py
```

Frontend:

```powershell
python -m http.server 8001 -d frontend
```

Open `http://127.0.0.1:8001`.

## Configuration

Copy `backend/.env.example` to `backend/.env` and adjust values as needed.

Common production defaults:

```env
HOST=127.0.0.1
PORT=10004
VAULT_PATH=./data/secretbase.enc
BACKUP_DIR=./data/backups/
CORS_ORIGINS=https://your-domain.example
```

AI parsing is optional. Leave `DEEPSEEK_API_KEY` empty to disable it.

## Verification

```powershell
python -m compileall backend
$env:DEEPSEEK_API_KEY=''; $env:AI_API_KEY=''; python scripts\v1-fake-smoke-test.py
node --check frontend\js\app.js
node --check frontend\js\api.js
node --check frontend\js\store.js
node --check frontend\js\utils.js
```

The fake smoke test uses a temporary vault and does not touch your real data.

## Documentation

- `docs/deployment.md`: generic deployment notes.
- `docs/api-specification.md`: API overview.
- `docs/security-design.md`: security model and vault format.
- `docs/frontend-design.md`: frontend structure and UX notes.
- `docs/release-safety-checklist.md`: release safety checklist.

## License

MIT License. See `LICENSE`.
