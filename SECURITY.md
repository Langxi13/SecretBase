# Security Policy

SecretBase stores sensitive data. Treat every vault file and backup as confidential.

## Do Not Commit

- `backend/.env`
- `backend/data/`
- `backend/logs/`
- `backend/settings.json`
- Any `secretbase.enc` file or `.bak` backup
- API keys, passwords, tokens, or real deployment credentials

## Supported Scope

This project is designed as a single-user password vault. It does not provide multi-user registration, shared vault permissions, or centralized account recovery.

## Reporting Security Issues

For private repository use, contact the maintainer directly or use GitHub private vulnerability reporting if enabled. Do not disclose vulnerabilities publicly before the maintainer has had time to respond.

## Production Recommendations

- Bind the backend to `127.0.0.1`.
- Put nginx or another reverse proxy in front of the backend.
- Use HTTPS.
- Add Basic Auth, VPN, or a zero-trust gateway for public deployments.
- Keep encrypted backups and test restore flows safely.
