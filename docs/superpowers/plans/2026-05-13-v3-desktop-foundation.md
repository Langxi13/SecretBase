# V3 Desktop Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build SecretBase V3.0 desktop foundation: local desktop launch mode, explicit runtime configuration, same-origin frontend hosting, desktop launcher, and verification without packaging a desktop app.

**Architecture:** Keep the current FastAPI + Vue CDN architecture. Add a centralized backend runtime configuration object while preserving existing config constants, then add a desktop launcher that sets desktop-specific environment before importing/running the backend. In desktop mode, FastAPI serves the existing frontend and a runtime config script from the same origin.

**Tech Stack:** Python 3, FastAPI, Uvicorn, Vue 3 CDN, plain JavaScript/CSS, shell scripts, Git worktrees.

---

## Current Context

- Current branch: `main`.
- Current remote baseline: `origin/main` at `bc642dc`.
- Current uncommitted docs before implementation: `README.md`, `docs/roadmap.md`, `docs/app-roadmap.md`, `docs/v3-desktop-foundation.md`, plus this plan.
- Do not push during V3.0 implementation.
- The user requested: write the plan first, preserve enough context for session compaction, then execute the plan.

## File Structure

- Modify `backend/config.py`: introduce `RuntimeConfig`, `load_runtime_config()`, `ensure_runtime_dirs()`, `is_desktop_mode()`, and compatibility constants.
- Modify `backend/main.py`: call explicit runtime directory setup, expose `/secretbase-runtime-config.js`, and mount frontend static files in desktop mode.
- Modify `frontend/index.html`: load `/secretbase-runtime-config.js` before `frontend/js/api.js`.
- Modify `frontend/js/api.js`: read `window.SECRETBASE_RUNTIME_CONFIG.apiBaseUrl`, preserve existing `window.SECRETBASE_API_BASE_URL`, and allow empty string API base for same-origin top-level APIs.
- Create `desktop/launcher.py`: desktop entrypoint, dry-run, no-browser mode, random port, child process lifecycle, and health checks.
- Create `scripts/test-desktop-foundation.py`: focused automated checks for config, launcher dry-run/no-browser, path isolation, and health endpoint.
- Modify `.gitignore`: add `.worktrees/` in a separate local commit before creating the implementation worktree.
- Modify `docs/v3-desktop-foundation.md` and `docs/app-roadmap.md` only if implementation discovers a documentation mismatch.

## Git Sequence

### Task 0: Commit Planning Baseline on `main`

**Files:**
- Add: `docs/superpowers/plans/2026-05-13-v3-desktop-foundation.md`
- Modify: `README.md`
- Modify: `docs/roadmap.md`
- Add: `docs/app-roadmap.md`
- Add: `docs/v3-desktop-foundation.md`

- [ ] **Step 1: Verify planning docs have no obvious placeholders**

Run from the implementation worktree. If the worktree does not contain `venv/`, use `/usr/local/Web-Project/Secert-Base/venv/bin/python` in place of `venv/bin/python`.

Run:

```bash
rg -n "TBD|待定|以后再说|%APPDATA%" README.md docs/roadmap.md docs/app-roadmap.md docs/v3-desktop-foundation.md
```

Expected: no matches.

- [ ] **Step 2: Verify diff whitespace**

Run from the implementation worktree. If the worktree does not contain `venv/`, use `/usr/local/Web-Project/Secert-Base/venv/bin/python` in place of `venv/bin/python`.

Run:

```bash
git diff --check
```

Expected: exit 0.

- [ ] **Step 3: Commit planning baseline locally**

Run:

```bash
git add README.md docs/roadmap.md docs/app-roadmap.md docs/v3-desktop-foundation.md docs/superpowers/plans/2026-05-13-v3-desktop-foundation.md
git commit -m "docs: plan v3 desktop foundation"
```

Expected: local commit on `main`; do not push.

### Task 1: Prepare Worktree Ignore Rule

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add `.worktrees/` to `.gitignore`**

Add this under local planning/session notes or local environments:

```gitignore
.worktrees/
```

- [ ] **Step 2: Verify ignore rule**

Run:

```bash
git check-ignore -q .worktrees
```

Expected: exit 0.

- [ ] **Step 3: Commit ignore rule locally**

Run:

```bash
git add .gitignore
git commit -m "chore: ignore local worktrees"
```

Expected: local commit on `main`; do not push.

### Task 2: Create Implementation Worktree

**Files:**
- Worktree path: `.worktrees/v3-desktop-foundation`
- Branch: `feature/v3-desktop-foundation`

- [ ] **Step 1: Create feature worktree**

Run:

```bash
git worktree add .worktrees/v3-desktop-foundation -b feature/v3-desktop-foundation
```

Expected: worktree created.

- [ ] **Step 2: Check worktree status**

Run:

```bash
git -C .worktrees/v3-desktop-foundation status --short --branch
```

Expected: clean worktree on `feature/v3-desktop-foundation`.

- [ ] **Step 3: Run baseline checks in worktree**

Run:

```bash
python -m compileall backend
node --check frontend/js/app.js frontend/js/api.js frontend/js/store.js frontend/js/utils.js
venv/bin/python scripts/test-backup-separation.py
venv/bin/python scripts/v1-fake-smoke-test.py
```

Expected: all pass. If baseline fails, stop and diagnose before implementation.

## Implementation Tasks

### Task 3: Runtime Config Object and Explicit Directory Initialization

**Files:**
- Modify: `backend/config.py`
- Create initially through tests: `scripts/test-desktop-foundation.py`

- [ ] **Step 1: Write failing config tests**

Create `scripts/test-desktop-foundation.py` with tests that import `backend/config.py` under controlled environment and assert:

```python
def test_server_mode_loads_dotenv_without_overriding_system_env():
    ...

def test_desktop_mode_does_not_load_backend_dotenv():
    ...

def test_importing_config_does_not_create_runtime_directories():
    ...

def test_ensure_runtime_dirs_creates_required_directories():
    ...
```

The script should use subprocesses or isolated module loading so each scenario gets a fresh `config` import.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
venv/bin/python scripts/test-desktop-foundation.py
```

Expected: fails because `RuntimeConfig`, desktop mode behavior, and explicit directory initialization are not implemented.

- [ ] **Step 3: Implement minimal config changes**

In `backend/config.py`:

- Add `APP_MODE = os.getenv("SECRETBASE_MODE", "server").strip().lower() or "server"`.
- Add `is_desktop_mode()`.
- Add `RuntimeConfig` dataclass.
- Add `load_runtime_config()`.
- Keep compatibility constants: `DATA_DIR`, `BACKUP_DIR`, `LOG_DIR`, `PORT`, `HOST`, `VAULT_PATH`, `SETTINGS_PATH`, `CORS_ORIGINS`, `LOG_LEVEL`, `LOG_DIR_PATH`.
- Move directory creation out of import time into `ensure_runtime_dirs()`.
- In server mode, load `backend/.env` with system environment priority.
- In desktop mode, do not load `backend/.env`.

- [ ] **Step 4: Run config tests and verify GREEN**

Run:

```bash
venv/bin/python scripts/test-desktop-foundation.py
```

Expected: config tests pass.

- [ ] **Step 5: Run backend regression checks**

Run:

```bash
python -m compileall backend
venv/bin/python scripts/test-backup-separation.py
venv/bin/python scripts/v1-fake-smoke-test.py
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/config.py scripts/test-desktop-foundation.py
git commit -m "feat: add explicit runtime config"
```

### Task 4: Desktop Same-Origin Frontend Hosting and Runtime Config Script

**Files:**
- Modify: `backend/main.py`
- Modify: `frontend/index.html`
- Modify: `frontend/js/api.js`
- Modify: `scripts/test-desktop-foundation.py`

- [ ] **Step 1: Add failing tests**

Extend `scripts/test-desktop-foundation.py` to assert:

```python
def test_runtime_config_endpoint_returns_javascript():
    ...

def test_desktop_mode_serves_frontend_index():
    ...
```

The test should start a subprocess backend in desktop mode with a temporary data root and query:

- `GET /health`
- `GET /secretbase-runtime-config.js`
- `GET /`

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
venv/bin/python scripts/test-desktop-foundation.py
```

Expected: fails because runtime config endpoint and desktop static hosting do not exist.

- [ ] **Step 3: Implement minimal backend/frontend changes**

In `backend/main.py`:

- Import `is_desktop_mode`, `ensure_runtime_dirs`, and `BASE_DIR`.
- Call `ensure_runtime_dirs()` before logging setup needs log directory.
- Add `GET /secretbase-runtime-config.js` returning JavaScript.
- In desktop mode, serve `frontend/index.html` at `/` and static assets under their existing relative paths.
- Keep API routers unchanged.

In `frontend/index.html`:

- Load `/secretbase-runtime-config.js` before `frontend/js/api.js`.

In `frontend/js/api.js`:

- Prefer `window.SECRETBASE_RUNTIME_CONFIG.apiBaseUrl` when present.
- Preserve `window.SECRETBASE_API_BASE_URL`.
- Allow empty string as a valid normalized base URL.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
venv/bin/python scripts/test-desktop-foundation.py
node --check frontend/js/api.js
python -m compileall backend
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/main.py frontend/index.html frontend/js/api.js scripts/test-desktop-foundation.py
git commit -m "feat: serve desktop frontend locally"
```

### Task 5: Desktop Launcher

**Files:**
- Create: `desktop/launcher.py`
- Modify: `scripts/test-desktop-foundation.py`

- [ ] **Step 1: Add failing launcher tests**

Extend `scripts/test-desktop-foundation.py` to assert:

```python
def test_launcher_dry_run_reports_desktop_paths():
    ...

def test_launcher_no_browser_starts_health_endpoint():
    ...
```

Tests should use `SECRETBASE_DESKTOP_DATA_ROOT` under `/tmp` and avoid opening a browser.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
venv/bin/python scripts/test-desktop-foundation.py
```

Expected: fails because `desktop/launcher.py` does not exist.

- [ ] **Step 3: Implement launcher**

Create `desktop/launcher.py` with:

- `--dry-run`
- `--no-browser`
- random port allocation bound to `127.0.0.1`
- desktop data root selection:
  - `SECRETBASE_DESKTOP_DATA_ROOT` if set
  - Windows `%LOCALAPPDATA%\SecretBase`
  - Linux/macOS development fallback under user data-style directory
- child process start for backend
- `/health` polling for 15 seconds
- failed startup output showing last 50 captured lines and log path
- `Ctrl+C` termination with 5 second graceful wait then force kill

- [ ] **Step 4: Run launcher tests and verify GREEN**

Run:

```bash
venv/bin/python scripts/test-desktop-foundation.py
```

Expected: pass.

- [ ] **Step 5: Run regression checks**

Run:

```bash
python -m compileall backend desktop scripts
node --check frontend/js/app.js frontend/js/api.js frontend/js/store.js frontend/js/utils.js
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add desktop/launcher.py scripts/test-desktop-foundation.py
git commit -m "feat: add desktop launcher"
```

### Task 6: Documentation and Developer Commands

**Files:**
- Modify: `docs/v3-desktop-foundation.md`
- Modify: `docs/app-roadmap.md` if needed
- Modify: `README.md` if a concise desktop development command is warranted

- [ ] **Step 1: Update documentation**

Ensure docs describe:

- `python desktop/launcher.py`
- `python desktop/launcher.py --no-browser`
- `python desktop/launcher.py --dry-run`
- `SECRETBASE_DESKTOP_DATA_ROOT`
- `/tmp/secretbase-v3-desktop-smoke` manual smoke directory
- V3.0 still does not package pywebview or PyInstaller

- [ ] **Step 2: Run doc and syntax checks**

Run:

```bash
rg -n "TBD|待定|以后再说|%APPDATA%" README.md docs/app-roadmap.md docs/v3-desktop-foundation.md
git diff --check
```

Expected: no placeholder or old Windows roaming path matches; diff check exits 0.

- [ ] **Step 3: Commit docs**

Run:

```bash
git add README.md docs/app-roadmap.md docs/v3-desktop-foundation.md docs/superpowers/plans/2026-05-13-v3-desktop-foundation.md
git commit -m "docs: document desktop foundation workflow"
```

## Final Verification

- [ ] **Run all required checks**

Run:

```bash
python -m compileall backend desktop scripts
node --check frontend/js/app.js frontend/js/api.js frontend/js/store.js frontend/js/utils.js
venv/bin/python scripts/test-desktop-foundation.py
venv/bin/python scripts/test-backup-separation.py
venv/bin/python scripts/v1-fake-smoke-test.py
```

Expected: all pass.

- [ ] **Run manual smoke without real vault**

Run:

```bash
SECRETBASE_DESKTOP_DATA_ROOT=/tmp/secretbase-v3-desktop-smoke python desktop/launcher.py --no-browser
```

Then query the printed URL or `/health`. For browser smoke, run without `--no-browser` if a GUI environment is available.

- [ ] **Confirm Git state**

Run:

```bash
git status --short --branch
git log --oneline -8
```

Expected: clean feature worktree after final commit; main worktree remains on local `main` with planning and worktree-prep commits, not pushed.

## Handoff Notes for Session Compaction

- Active implementation branch should be `feature/v3-desktop-foundation` in `.worktrees/v3-desktop-foundation`.
- Do not push remote until user explicitly asks.
- Do not use real vault files during desktop testing.
- Keep V3.0 scoped to foundation only; PyInstaller, pywebview, installer, tray, and Windows formal acceptance remain V3.1.
