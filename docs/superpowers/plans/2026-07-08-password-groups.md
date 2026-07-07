# Password Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add album-like password groups and selectable existing tags to the SecretBase frontend and backend.

**Architecture:** Extend the existing vault entry model with `groups`, add `groups_meta` to vault data, and implement `/groups` routes following the existing `/tags` route style. The frontend keeps the static Vue CDN architecture and adds a password group mode in the existing workspace.

**Tech Stack:** FastAPI, Pydantic, plain Vue 3 CDN, plain JavaScript, CSS, shell/Node/Python smoke scripts.

---

### Task 1: Backend Group Model And Routes

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/routes/entries.py`
- Create: `backend/routes/groups.py`
- Modify: `backend/main.py`
- Test: `scripts/test-password-groups.py`

- [x] Write a failing script that creates grouped entries, lists groups, and filters by group.
- [x] Add `groups` to entries and `groups_meta` to vault data.
- [x] Add `/groups` list/create/update/delete routes.
- [x] Add `group` query support to `/entries`.

### Task 2: Frontend Group Mode And Entry Editing

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/js/app.js`
- Modify: `frontend/js/store.js`
- Modify: `frontend/css/style.css`
- Modify: `frontend/css/components.css`

- [x] Add password group mode in the sidebar.
- [x] Add group cards in the main workspace.
- [x] Add existing tag chips to the entry editor.
- [x] Add group chips and inline group input to the entry editor.
- [x] Add group filtering and clear behavior.

### Task 3: Docs, Cache Version, Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/api-specification.md`
- Modify: `docs/frontend-design.md`
- Modify: `frontend/index.html`

- [x] Document group API and frontend behavior.
- [x] Bump frontend static asset version.
- [x] Run backend/frontend checks and smoke tests.
