# UI Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the SecretBase frontend into a more polished Chinese-first password vault UI without changing existing API contracts or core behavior.

**Architecture:** Keep the current Vue 3 CDN, static HTML template, and plain CSS structure. Concentrate visual changes in `frontend/css/themes/*.css`, `frontend/css/style.css`, and `frontend/css/components.css`; make only small `frontend/index.html` and `frontend/js/app.js` changes when needed to fix visible interaction bugs or add non-disruptive UI hooks.

**Tech Stack:** Vue 3 CDN, plain JavaScript, Fetch API, plain CSS with CSS variables, FastAPI static frontend serving.

---

## Files and Responsibilities

- `frontend/css/themes/variables.css`: shared design tokens for surface layers, colors, borders, shadows, focus rings, and fixed UI sizing.
- `frontend/css/themes/dark.css`: primary premium dark theme overrides.
- `frontend/css/themes/light.css`: light theme compatibility overrides.
- `frontend/css/themes/system.css`: system dark-mode overrides matching `dark.css`.
- `frontend/css/style.css`: application shell, auth screens, sidebar, header, search/filter panel, entry cards, pagination, mobile layout, and bottom action bars.
- `frontend/css/components.css`: modal surfaces, forms, tags, AI parse UI, backup center, settings/tools/tag/trash/import/restore components, Toast, and responsive modal behavior.
- `frontend/index.html`: only add harmless classes, wrapper hooks, or Chinese text refinements needed by the CSS.
- `frontend/js/app.js`: only fix frontend-visible interaction bugs discovered during the redesign, such as stale overlays or outside-click handling. Do not alter API semantics.
- `docs/superpowers/specs/2026-07-07-ui-visual-redesign-design.md`: source specification, already approved.

## Task 1: Baseline and Safety Checks

**Files:**
- Read: `frontend/index.html`
- Read: `frontend/js/app.js`
- Read: `frontend/css/style.css`
- Read: `frontend/css/components.css`
- Read: `frontend/css/themes/variables.css`
- Read: `frontend/css/themes/dark.css`
- Read: `frontend/css/themes/light.css`
- Read: `frontend/css/themes/system.css`

- [ ] **Step 1: Capture current frontend syntax baseline**

Run:

```bash
node --check frontend/js/api.js
node --check frontend/js/store.js
node --check frontend/js/app.js
```

Expected: all three commands exit `0`.

- [ ] **Step 2: Locate current UI hooks before editing**

Run:

```bash
rg -n "app-container|desktop-sidebar|workspace-shell|app-header|search-bar|entry-card|modal-overlay|backup-center-modal|settings-modal|tag-browser-modal|bottom" frontend/index.html frontend/css frontend/js/app.js
```

Expected: output shows the main shell, card, modal, backup, settings, tag browser, and mobile/bottom bar selectors.

- [ ] **Step 3: Commit nothing**

No commit is needed for this baseline task. Continue only after the baseline commands pass.

## Task 2: Refresh Theme Tokens

**Files:**
- Modify: `frontend/css/themes/variables.css`
- Modify: `frontend/css/themes/dark.css`
- Modify: `frontend/css/themes/light.css`
- Modify: `frontend/css/themes/system.css`

- [ ] **Step 1: Replace shared tokens in `variables.css`**

Add stable surface, border, shadow, focus, status, and sizing variables while preserving existing variable names used by the app:

```css
:root {
    color-scheme: light;
    --color-primary: #2563eb;
    --color-primary-hover: #1d4ed8;
    --color-primary-light: rgba(37, 99, 235, 0.12);
    --color-accent: #0f766e;
    --color-success: #16a34a;
    --color-warning: #d97706;
    --color-error: #dc2626;
    --color-info: #0284c7;
    --bg-primary: #f5f7fb;
    --bg-secondary: #edf2f7;
    --bg-card: #ffffff;
    --bg-elevated: rgba(255, 255, 255, 0.92);
    --bg-sunken: #e8edf5;
    --bg-overlay-soft: rgba(15, 23, 42, 0.08);
    --bg-modal: rgba(15, 23, 42, 0.58);
    --surface-1: #ffffff;
    --surface-2: #f9fbff;
    --surface-3: #eef3fa;
    --text-primary: #172033;
    --text-secondary: #536176;
    --text-tertiary: #7b8798;
    --text-muted: #98a3b3;
    --text-inverse: #ffffff;
    --border-color: #d8e1ee;
    --border-strong: #c6d2e3;
    --border-subtle: rgba(15, 23, 42, 0.08);
    --border-radius: 8px;
    --border-radius-lg: 14px;
    --border-radius-xl: 18px;
    --focus-ring: 0 0 0 3px rgba(37, 99, 235, 0.18);
    --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.06);
    --shadow-md: 0 14px 34px rgba(15, 23, 42, 0.10);
    --shadow-lg: 0 26px 70px rgba(15, 23, 42, 0.18);
    --shadow-glow: 0 0 0 1px rgba(37, 99, 235, 0.10), 0 18px 45px rgba(37, 99, 235, 0.14);
    --status-success-bg: rgba(22, 163, 74, 0.12);
    --status-warning-bg: rgba(217, 119, 6, 0.13);
    --status-error-bg: rgba(220, 38, 38, 0.12);
    --status-info-bg: rgba(2, 132, 199, 0.12);
    --control-height: 42px;
    --sidebar-width: 278px;
    --content-max-width: 1240px;
    --spacing-xs: 4px;
    --spacing-sm: 8px;
    --spacing-md: 16px;
    --spacing-lg: 24px;
    --spacing-xl: 32px;
    --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    --font-size-xs: 12px;
    --font-size-sm: 14px;
    --font-size-md: 16px;
    --font-size-lg: 18px;
    --font-size-xl: 20px;
    --transition-fast: 0.1s ease;
    --transition-normal: 0.2s ease;
    --transition-slow: 0.3s ease;
}
```

- [ ] **Step 2: Replace dark theme overrides**

Ensure `dark.css` uses premium dark surfaces without one-note purple/blue dominance:

```css
[data-theme="dark"] {
    color-scheme: dark;
    --color-primary: #60a5fa;
    --color-primary-hover: #93c5fd;
    --color-primary-light: rgba(96, 165, 250, 0.16);
    --color-accent: #2dd4bf;
    --color-success: #34d399;
    --color-warning: #fbbf24;
    --color-error: #fb7185;
    --color-info: #38bdf8;
    --bg-primary: #090f1a;
    --bg-secondary: #0e1624;
    --bg-card: #121b2b;
    --bg-elevated: rgba(18, 27, 43, 0.94);
    --bg-sunken: #070c14;
    --bg-overlay-soft: rgba(148, 163, 184, 0.08);
    --bg-modal: rgba(3, 7, 18, 0.72);
    --surface-1: #111827;
    --surface-2: #162235;
    --surface-3: #1d2b42;
    --text-primary: #f4f7fb;
    --text-secondary: #bfcbda;
    --text-tertiary: #8ea0b8;
    --text-muted: #6f7f95;
    --border-color: rgba(148, 163, 184, 0.22);
    --border-strong: rgba(148, 163, 184, 0.36);
    --border-subtle: rgba(148, 163, 184, 0.12);
    --focus-ring: 0 0 0 3px rgba(96, 165, 250, 0.22);
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.35);
    --shadow-md: 0 18px 45px rgba(0, 0, 0, 0.28);
    --shadow-lg: 0 32px 90px rgba(0, 0, 0, 0.46);
    --shadow-glow: 0 0 0 1px rgba(96, 165, 250, 0.20), 0 22px 60px rgba(37, 99, 235, 0.22);
    --status-success-bg: rgba(52, 211, 153, 0.13);
    --status-warning-bg: rgba(251, 191, 36, 0.14);
    --status-error-bg: rgba(251, 113, 133, 0.14);
    --status-info-bg: rgba(56, 189, 248, 0.14);
}
```

- [ ] **Step 3: Expand light and system theme compatibility**

Keep `light.css` explicit and mirror dark variables inside the dark media query in `system.css`.

- [ ] **Step 4: Run quick syntax check**

Run:

```bash
node --check frontend/js/app.js
```

Expected: exits `0` because this task should not affect JavaScript.

- [ ] **Step 5: Commit**

```bash
git add frontend/css/themes/variables.css frontend/css/themes/dark.css frontend/css/themes/light.css frontend/css/themes/system.css
git commit -m "style: refresh frontend theme tokens"
```

## Task 3: Polish App Shell, Sidebar, Search, and Entry Cards

**Files:**
- Modify: `frontend/css/style.css`
- Modify: `frontend/index.html` only if a non-behavioral class hook is needed

- [ ] **Step 1: Add base polish in `style.css`**

Update base styles for body background, form controls, focus states, scroll behavior, and buttons. The implementation must keep all current class names active. Add or update these selectors:

```css
body {
    background:
        radial-gradient(circle at top left, rgba(96, 165, 250, 0.10), transparent 32rem),
        linear-gradient(135deg, var(--bg-primary), var(--bg-secondary));
    min-height: 100vh;
}

button:focus-visible,
input:focus-visible,
select:focus-visible,
textarea:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
}

input,
select,
textarea {
    border: 1px solid var(--border-color);
    min-height: var(--control-height);
}
```

- [ ] **Step 2: Redesign desktop shell and sidebar**

In the existing desktop media query, make `.app-container`, `.desktop-sidebar`, `.workspace-shell`, `.sidebar-brand`, `.sidebar-create`, `.sidebar-section`, and `.sidebar-nav-item` look like a polished application shell. Preserve existing navigation buttons and click handlers.

- [ ] **Step 3: Redesign header and search panel**

Update `.app-header`, `.search-bar`, `.search-input`, `.search-scope-selector`, `.search-scope-chip`, `.sort-controls`, `.advanced-filters`, `.advanced-filter-panel`, `.active-filter-chips`, and `.list-context-notice` so the search/filter area reads as one command panel with clear grouping.

- [ ] **Step 4: Redesign entry cards**

Update `.entries-list`, `.entry-card`, `.entry-header`, `.entry-title`, `.entry-tags`, `.tag`, `.entry-fields`, `.field-row`, `.entry-actions`, `.copy-dropdown`, `.copy-menu`, `.pagination`, and empty/list states. Ensure long titles and tags wrap:

```css
.entry-card,
.backup-item,
.tag,
.filter-chip {
    overflow-wrap: anywhere;
}
```

- [ ] **Step 5: Rework mobile shell**

In mobile media queries, ensure `.app-header`, `.search-bar`, `.entries-list`, `.entry-card`, `.bottom-actions`, and `.pagination` do not overflow or get covered. Add bottom padding to the main content so the fixed bottom actions do not hide cards.

- [ ] **Step 6: Run syntax checks**

Run:

```bash
node --check frontend/js/api.js
node --check frontend/js/store.js
node --check frontend/js/app.js
```

Expected: all exit `0`.

- [ ] **Step 7: Commit**

```bash
git add frontend/css/style.css frontend/index.html
git commit -m "style: polish main SecretBase workspace"
```

## Task 4: Polish Modals, Forms, Backups, Settings, AI, and Tools

**Files:**
- Modify: `frontend/css/components.css`
- Modify: `frontend/index.html` only if a non-behavioral class hook is needed

- [ ] **Step 1: Redesign modal surfaces**

Update `.modal-overlay`, `.modal-content`, `.modal-header`, `.modal-body`, `.modal-footer`, `.modal-close`, `.warning-panel`, `.info-panel`, `.error-message`, and `.confirm-dialog`. Desktop modals should look elevated; mobile modals should fit the viewport and keep action buttons reachable.

- [ ] **Step 2: Redesign form and tag components**

Update `.form-group`, `.form-row`, `.fields-editor`, `.tags-input`, `.checkbox-label`, `.template-selector`, `.settings-row`, `.settings-list`, and tag chip styles. Keep labels and existing inputs intact.

- [ ] **Step 3: Redesign AI parse UI**

Update `.ai-parse-result`, `.ai-parse-entry`, `.ai-entry-select`, `.ai-edit-grid`, `.ai-field-editor`, `.ai-field-row`, `.ai-input-meta`, `.ai-quality-warning`, and `.ai-failure-panel`. Ensure multi-result editing remains clear and all messages stay Chinese.

- [ ] **Step 4: Redesign backup center and restore wizard**

Update `.backup-center-modal`, `.backup-summary-grid`, `.backup-toolbar`, `.backup-list`, `.backup-group`, `.backup-item`, `.backup-item-actions`, `.backup-pagination`, `.restore-wizard-modal`, and restore step indicators. Long filenames must wrap and action buttons must not collapse into unreadable text.

- [ ] **Step 5: Redesign settings, tools, tag manager, trash, import preview**

Update `.settings-modal`, `.settings-tabs`, `.settings-tab`, `.settings-section`, `.tools-modal`, `.tag-manager-modal`, `.tag-browser-modal`, `.trash-item`, `.import-preview-*`, and `.import-report-modal` selectors that already exist in `components.css`.

- [ ] **Step 6: Run syntax checks**

Run:

```bash
node --check frontend/js/api.js
node --check frontend/js/store.js
node --check frontend/js/app.js
```

Expected: all exit `0`.

- [ ] **Step 7: Commit**

```bash
git add frontend/css/components.css frontend/index.html
git commit -m "style: polish SecretBase dialogs and tools"
```

## Task 5: Fix Visible Frontend Interaction Bugs

**Files:**
- Modify: `frontend/js/app.js`
- Modify: `frontend/index.html` if event modifiers are needed
- Modify: `frontend/css/style.css`
- Modify: `frontend/css/components.css`

- [ ] **Step 1: Inspect outside-click and unauthorized handling**

Run:

```bash
rg -n "secretbase:unauthorized|addEventListener|removeEventListener|click|showTagDropdown|copyMenuEntryId|showTagBrowser|showAdvancedFilters|locked.value|api.setToken" frontend/js/app.js frontend/index.html
```

Expected: output includes the unauthorized event handler, global click listeners if present, tag dropdown state, copy menu state, tag browser state, and lock handling.

- [ ] **Step 2: Ensure 401 clears unlocked state**

If not already present, make the `secretbase:unauthorized` handler clear token, close sensitive overlays, and return to the locked screen:

```javascript
const handleUnauthorized = (event) => {
    api.setToken(null);
    locked.value = true;
    password.value = '';
    selectedEntry.value = null;
    editingEntry.value = null;
    showCreateModal.value = false;
    showEditModal.value = false;
    showAiParse.value = false;
    showSettings.value = false;
    showTrash.value = false;
    showTagManager.value = false;
    showTagBrowser.value = false;
    showBackupCenter.value = false;
    showTools.value = false;
    showImportPreview.value = false;
    showImportConflicts.value = false;
    showImportReport.value = false;
    copyMenuEntryId.value = null;
    showTagDropdown.value = false;
    unlockError.value = event?.detail?.message || '请先解锁';
};
```

- [ ] **Step 3: Ensure floating menus close predictably**

If click-outside handling is incomplete, add a document click handler that closes copy menus, tag dropdowns, and tag browser transient state without closing normal modals unexpectedly:

```javascript
const handleDocumentClick = (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (!target.closest('.copy-dropdown')) {
        copyMenuEntryId.value = null;
    }
    if (!target.closest('.tag-dropdown-wrapper')) {
        showTagDropdown.value = false;
    }
};
```

Register it on mount and remove it on unmount if `onUnmounted` is imported; otherwise keep the existing lifecycle style and avoid duplicate listeners.

- [ ] **Step 4: Add missing CSS hooks only when required**

If `.tag-dropdown-wrapper` is not present around the tag dropdown trigger and menu, add it in `frontend/index.html` without changing button handlers.

- [ ] **Step 5: Run syntax checks**

Run:

```bash
node --check frontend/js/api.js
node --check frontend/js/store.js
node --check frontend/js/app.js
```

Expected: all exit `0`.

- [ ] **Step 6: Commit**

```bash
git add frontend/js/app.js frontend/index.html frontend/css/style.css frontend/css/components.css
git commit -m "fix: tighten frontend overlay state handling"
```

## Task 6: Local Visual QA and Final Verification

**Files:**
- Read: all modified frontend files
- Optional modify: `frontend/css/style.css`, `frontend/css/components.css`, `frontend/js/app.js` for QA fixes only

- [ ] **Step 1: Start a local backend or desktop mode**

Preferred desktop-safe manual command:

```bash
SECRETBASE_DESKTOP_DATA_ROOT=/tmp/secretbase-ui-redesign-test python desktop/launcher.py --no-browser
```

Expected: command prints a local URL and keeps serving the app.

- [ ] **Step 2: If using static frontend mode, start frontend server**

Only use this if testing against an already running backend:

```bash
python -m http.server 8001 -d frontend
```

Expected: frontend available at `http://127.0.0.1:8001`.

- [ ] **Step 3: Manually check core screens**

Check these screens in Chinese:

```text
未初始化
锁定/解锁
主界面
条目详情
新建条目
编辑条目
AI 智能录入
备份中心
恢复向导
设置
工具
标签管理
更多标签
回收站
导入预览
导入完成报告
确认弹窗
```

- [ ] **Step 4: Check responsive widths**

Use browser responsive mode at:

```text
390x844
768x1024
1440x900
```

Expected: no horizontal overflow, no hidden modal buttons, bottom actions do not cover the last card, long text wraps.

- [ ] **Step 5: Final automated checks**

Run:

```bash
node --check frontend/js/api.js
node --check frontend/js/store.js
node --check frontend/js/app.js
git status --short
```

Expected: JS checks pass. `git status --short` is clean after final commit or shows only intentionally uncommitted QA notes.

- [ ] **Step 6: Final commit**

If QA fixes were needed after Task 5, commit them:

```bash
git add frontend/css/style.css frontend/css/components.css frontend/css/themes/variables.css frontend/css/themes/dark.css frontend/css/themes/light.css frontend/css/themes/system.css frontend/index.html frontend/js/app.js
git commit -m "style: finalize SecretBase visual refresh"
```

If no QA fixes were needed, skip this commit.
