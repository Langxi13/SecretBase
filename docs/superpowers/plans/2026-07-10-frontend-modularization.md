# Frontend Modularization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **状态：已完成（2026-07-10）**。最终实现进一步采用入口加载壳与同源模板片段，当前模块边界和验证项以 `docs/frontend-design.md` 为准；本文保留为重构实施记录。

**Goal:** Reduce the largest frontend file while keeping the current Vue CDN runtime, UI, and behavior intact.

**Architecture:** Keep `index.html` as the Vue template for this phase. Move low-coupling logic from `frontend/js/app.js` into plain browser modules that expose `window.SecretBase*` namespaces and are loaded before `app.js`.

**Tech Stack:** Vue 3 CDN, plain JavaScript, plain CSS, Node-based static checks, existing Python test scripts.

---

### Task 1: Guard The Split

**Files:**
- Create: `scripts/test-frontend-feature-modules.js`
- Modify: `frontend/index.html`
- Modify: `frontend/js/app.js`

- [x] Add a Node test that requires `view-helpers.js`, `tag-view.js`, `backup-view.js`, and `ai-view.js` to load before `app.js`.
- [x] Assert `frontend/js/app.js` is below 3100 lines after the split.
- [x] Assert app setup delegates AI summaries, tag view state, backup view state, and card helper logic to module namespaces.
- [x] Run `node scripts/test-frontend-feature-modules.js` and confirm it fails before implementation.

### Task 2: Extract Stable View Helpers

**Files:**
- Create: `frontend/js/view-helpers.js`
- Modify: `frontend/js/app.js`
- Modify: `frontend/index.html`

- [x] Move URL favicon, date formatting, field hidden normalization, entry/group color styling, group chip helpers, byte formatting, backup type labels, API error message formatting, and AI label helpers into `window.SecretBaseViewHelpers`.
- [x] Replace the removed local functions in `app.js` with module calls or thin wrappers where reactive state is needed.
- [x] Load `view-helpers.js` before `app.js`.

### Task 3: Extract Tag, Backup, And AI Computed Factories

**Files:**
- Create: `frontend/js/tag-view.js`
- Create: `frontend/js/backup-view.js`
- Create: `frontend/js/ai-view.js`
- Modify: `frontend/js/app.js`
- Modify: `frontend/index.html`

- [x] Move tag sorting, sidebar tag visibility, tag browser filtering, tag pagination, tag manager pagination, and managed-page selection computed factories into `SecretBaseTagView.createTagView`.
- [x] Move backup busy state, backup sorting, backup summary, and grouped backup pagination into `SecretBaseBackupView.createBackupView`.
- [x] Move AI organize/action summary and selected-count computed factories into `SecretBaseAiView.createAiView`.
- [x] Destructure returned computed values in `app.js` using the same names already returned to the template.

### Task 4: Verify And Deploy

**Files:**
- Modify: `README.md`
- Modify: `docs/frontend-design.md`

- [x] Update documentation to describe the new browser module namespaces.
- [x] Run all `scripts/test-frontend-*.js`.
- [x] Run `node --check frontend/js/*.js`.
- [x] Run `git diff --check`.
- [x] Run critical Python regressions with `venv/bin/python`.
- [x] Restart `secretbase`, reload `nginx`, and check `/health`.
- [x] Commit the change.
