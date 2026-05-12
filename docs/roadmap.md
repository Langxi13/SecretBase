# Roadmap

SecretBase is intentionally scoped as a single-user encrypted vault. The priority is reliability and safe long-term personal use, not multi-user collaboration.

## Current Focus

- Keep the encrypted vault format stable.
- Preserve safe backup, export, import, and restore flows.
- Maintain a simple FastAPI backend and Vue CDN frontend.
- Keep production deployment practical behind nginx or another reverse proxy.
- Track the long-term desktop and mobile app direction in [App Roadmap](app-roadmap.md).

## Implemented

- Master-password initialization, unlock, lock, and auto-lock.
- Entry CRUD with tags, custom fields, search, filters, sorting, pagination, and trash.
- Encrypted backups and plain JSON export/import.
- Optional DeepSeek-compatible AI-assisted parsing.
- Random session tokens and frontend `sessionStorage` token handling.
- File locking, optimistic write conflict detection, and atomic vault writes.
- Legacy encrypted backup compatibility with explicit backup password input.
- Security self-check endpoint for deployment configuration.

## Later, If Needed

- More polished mobile layouts.
- Better large-vault performance if real usage outgrows pagination.
- More compact and modular frontend organization.
- Additional production health check automation.
- Desktop and mobile app packaging, planned separately in [App Roadmap](app-roadmap.md).

## Out of Scope

- Multi-user registration or shared vault permissions.
- Database-backed storage.
- Browser-side vault encryption rewrite.
- Password generation.
- Automatic data migrations without explicit backup and restore rehearsal.
