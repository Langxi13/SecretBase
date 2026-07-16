# Roadmap

SecretBase is intentionally scoped as a single-user encrypted vault. The priority is reliability and safe long-term personal use, not multi-user collaboration.

## Current Focus

- Keep the encrypted vault format stable.
- Preserve safe backup, export, import, and restore flows.
- Maintain a simple FastAPI backend and vendored Vue frontend with no runtime CDN dependency.
- Keep production deployment practical behind nginx or another reverse proxy.
- Maintain the stable Windows and macOS desktop packaging, diagnostics, lifecycle, and data-safety behavior described in [App Roadmap](app-roadmap.md).
- Maintain the released Android-first Flutter/Rust client across hardware, encrypted migration, biometric unlock, AI safety, and three-ABI/API 29/36 gates.
- Maintain the released V5 signed-update baseline: Windows in-place updates, Android system-confirmed replacement, and macOS signed-manifest notifications.
- Keep Web, desktop, and Android AI plans behaviorally aligned while preserving the no-existing-field-values network boundary.

## Implemented

- Master-password initialization, unlock, lock, and auto-lock.
- Entry CRUD with tags, custom fields, search, filters, sorting, pagination, and trash.
- Encrypted backups and plain JSON export/import.
- Optional conversational AI manager with multiple editable OpenAI-compatible provider presets, encrypted history, metadata-only requests, and review-before-apply plans.
- Random session tokens and safe frontend `sessionStorage` handling with an in-memory fallback when site storage is unavailable.
- File locking, optimistic write conflict detection, and atomic vault writes.
- Legacy encrypted backup compatibility with explicit backup password input.
- Security self-check endpoint for deployment configuration.
- Offline-capable local desktop foundation with loopback-only startup and isolated user data paths.
- One-command Windows/Linux/macOS source startup and cross-platform release checks.
- PyInstaller/pywebview Windows one-folder packaging with native export dialogs, single-instance activation, artifact scanning, and two-version Windows CI.
- Windows V3.2 per-user installer, desktop diagnostics, optional tray, safe uninstall flow, native zoom feedback, and Windows 10/11 hardware acceptance.
- macOS V3.3 arm64 DMG/ZIP packaging, WKWebView lifecycle, native zoom controls, CI, and Apple Silicon hardware acceptance.
- Normative Vault V1 format documentation, public Python-compatible golden vectors, and an isolated Rust reference core.
- Android 10+ Flutter/Rust client with private storage, lifecycle locking, Keystore-backed biometric unlock, entries, tags, groups, trash, encrypted transfer, a conversational AI manager, and revision-bound AI undo.
- Signed stable update manifests, Windows installer handoff, Android package identity verification, and protected release-key environments.

## Later, If Needed

- iOS feasibility and adaptation after the stable V5.0.x maintenance line, with App Store signing and distribution requirements planned separately.
- Better large-vault performance if real usage outgrows pagination.
- More compact and modular frontend organization.
- Additional production health check automation.
- macOS signing and notarization when an Apple Developer account is available.
- Tablet-specific two-pane layouts and store distribution only after the signed Android MVP is stable.

## Out of Scope

- Multi-user registration or shared vault permissions.
- Database-backed storage.
- Browser-side vault encryption rewrite.
- Model-generated or remotely transmitted existing passwords; local secure generation may be offered as an explicit device-only action.
- Automatic data migrations without explicit backup and restore rehearsal.
