# Roadmap

SecretBase is intentionally scoped as a single-user encrypted vault. The priority is reliability and safe long-term personal use, not multi-user collaboration.

## Current Focus

- Keep the encrypted vault format stable.
- Preserve safe backup, export, import, and restore flows.
- Maintain a simple FastAPI backend and vendored Vue frontend with no runtime CDN dependency.
- Keep production deployment practical behind nginx or another reverse proxy.
- Complete Windows hardware acceptance for the implemented V3.1 desktop MVP described in [App Roadmap](app-roadmap.md).

## Implemented

- Master-password initialization, unlock, lock, and auto-lock.
- Entry CRUD with tags, custom fields, search, filters, sorting, pagination, and trash.
- Encrypted backups and plain JSON export/import.
- Optional DeepSeek-compatible AI-assisted parsing.
- Random session tokens and frontend `sessionStorage` token handling.
- File locking, optimistic write conflict detection, and atomic vault writes.
- Legacy encrypted backup compatibility with explicit backup password input.
- Security self-check endpoint for deployment configuration.
- Offline-capable local desktop foundation with loopback-only startup and isolated user data paths.
- One-command Windows/Linux/macOS source startup and cross-platform release checks.
- PyInstaller/pywebview Windows one-folder packaging with native export dialogs, single-instance activation, artifact scanning, and two-version Windows CI.

## Later, If Needed

- More polished mobile layouts.
- Better large-vault performance if real usage outgrows pagination.
- More compact and modular frontend organization.
- Additional production health check automation.
- Windows installer/signing improvements, followed by macOS and mobile work as staged in [App Roadmap](app-roadmap.md).

## Out of Scope

- Multi-user registration or shared vault permissions.
- Database-backed storage.
- Browser-side vault encryption rewrite.
- Password generation.
- Automatic data migrations without explicit backup and restore rehearsal.
