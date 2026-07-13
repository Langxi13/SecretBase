# Roadmap

SecretBase is intentionally scoped as a single-user encrypted vault. The priority is reliability and safe long-term personal use, not multi-user collaboration.

## Current Focus

- Keep the encrypted vault format stable.
- Preserve safe backup, export, import, and restore flows.
- Maintain a simple FastAPI backend and vendored Vue frontend with no runtime CDN dependency.
- Keep production deployment practical behind nginx or another reverse proxy.
- Maintain the stable Windows and macOS desktop packaging, diagnostics, lifecycle, and data-safety behavior described in [App Roadmap](app-roadmap.md).
- Finish CI, emulator, hardware, migration, and signing acceptance for the implemented Android-first Flutter/Rust client.

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
- Windows V3.2 per-user installer, desktop diagnostics, optional tray, safe uninstall flow, native zoom feedback, and Windows 10/11 hardware acceptance.
- macOS V3.3 arm64 DMG/ZIP packaging, WKWebView lifecycle, native zoom controls, CI, and Apple Silicon hardware acceptance.
- Normative Vault V1 format documentation, public Python-compatible golden vectors, and an isolated Rust reference core.
- Android 10+ Flutter/Rust client with private storage, lifecycle locking, entries, tags, groups, trash, encrypted transfer, and review-before-apply AI workflows.

## Later, If Needed

- Android hardware acceptance and later iOS adaptation after the V5 release gates pass.
- Better large-vault performance if real usage outgrows pagination.
- More compact and modular frontend organization.
- Additional production health check automation.
- macOS signing and notarization when an Apple Developer account is available.
- Tablet-specific layouts, biometrics, and store distribution only after the signed Android MVP is stable.

## Out of Scope

- Multi-user registration or shared vault permissions.
- Database-backed storage.
- Browser-side vault encryption rewrite.
- Password generation.
- Automatic data migrations without explicit backup and restore rehearsal.
