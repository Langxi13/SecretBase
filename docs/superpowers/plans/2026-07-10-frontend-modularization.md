# Frontend Modularization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the largest frontend file while keeping the current Vue CDN runtime, UI, and behavior intact.

**Architecture:** Keep `index.html` as the Vue template for this phase. Move low-coupling logic from `frontend/js/app.js` into plain browser modules that expose `window.SecretBase*` namespaces and are loaded before `app.js`.

**Tech Stack:** Vue 3 CDN, plain JavaScript, plain CSS, Node-based static checks, existing Python test scripts.

---

### Task 1: Guard The Split

**Files:**
- Create: `scripts/test-frontend-feature-modules.js`
- Modify: `frontend/index.html`
- Modify: `frontend/js/app.js`

- [ ] Add a Node test that requires `view-helpers.js`, `tag-view.js`, `backup-view.js`, and `ai-view.js` to load before `app.js`.
- [ ] Assert `frontend/js/app.js` is below 3100 lines after the split.
- [ ] Assert app setup delegates AI summaries, tag view state, backup view state, and card helper logic to module namespaces.
- [ ] Run `node scripts/test-frontend-feature-modules.js` and confirm it fails before implementation.

### Task 2: Extract Stable View Helpers

**Files:**
- Create: `frontend/js/view-helpers.js`
- Modify: `frontend/js/app.js`
- Modify: `frontend/index.html`

- [ ] Move URL favicon, date formatting, field hidden normalization, entry/group color styling, group chip helpers, byte formatting, backup type labels, API error message formatting, and AI label helpers into `window.SecretBaseViewHelpers`.
- [ ] Replace the removed local functions in `app.js` with module calls or thin wrappers where reactive state is needed.
- [ ] Load `view-helpers.js` before `app.js`.

### Task 3: Extract Tag, Backup, And AI Computed Factories

**Files:**
- Create: `frontend/js/tag-view.js`
- Create: `frontend/js/backup-view.js`
- Create: `frontend/js/ai-view.js`
- Modify: `frontend/js/app.js`
- Modify: `frontend/index.html`

- [ ] Move tag sorting, sidebar tag visibility, tag browser filtering, tag pagination, tag manager pagination, and managed-page selection computed factories into `SecretBaseTagView.createTagView`.
- [ ] Move backup busy state, backup sorting, backup summary, and grouped backup pagination into `SecretBaseBackupView.createBackupView`.
- [ ] Move AI organize/action summary and selected-count computed factories into `SecretBaseAiView.createAiView`.
- [ ] Destructure returned computed values in `app.js` using the same names already returned to the template.

### Task 4: Verify And Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/frontend-design.md`

- [ ] Update documentation to describe the new browser module namespaces.
- [ ] Run all `scripts/test-frontend-*.js`.
- [ ] Run `node --check frontend/js/*.js`.
- [ ] Run `git diff --check`.
- [ ] Run critical Python regressions with `venv/bin/python`.
- [ ] Restart `secretbase`, reload `nginx`, and check `/health`.
- [ ] Commit the change.
