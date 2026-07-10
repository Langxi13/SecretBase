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
- Keep `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, and `X-Content-Type-Options: nosniff` on frontend responses.
- Do not replace the vendored Vue runtime with an unpinned CDN script.
- Do not add third-party favicon, analytics, font, or telemetry requests to vault screens; entry domains are sensitive metadata.

## Desktop Foundation Security

- Desktop mode must listen only on `127.0.0.1` and use a random port.
- Desktop CORS must allow only the current loopback origin.
- Desktop Host validation must accept only `127.0.0.1` and `localhost`.
- Local runtime data must remain outside the repository and be accessible only to the current OS user where the platform permits.
- The V3.0 browser launcher is not a signed desktop package; Windows packaging and signing are tracked separately.
