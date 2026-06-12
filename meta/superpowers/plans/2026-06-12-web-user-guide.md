# Web User Guide Documentation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Chinese user-facing web guide that explains the current AudioQAS pages and flows from a PC browser user's perspective, and expose it from the root README with a single stable link.

**Architecture:** Treat the guide as product-adjacent documentation grounded only in the current `web-preview` runtime behavior. Keep the delivered guide in `docs/` as Chinese Markdown for easy review and iteration, and keep the README change minimal by adding only one documentation entry.

**Tech Stack:** Markdown, existing product docs, current static web preview sources.

---

### Task 1: Confirm Current Product Boundary

**Files:**
- Read: `docs/web-product-spec.md`
- Read: `audioqas/web/static/web-preview-data.js`
- Read: `audioqas/web/static/web-preview-app.js`

- [x] Check current page structure and supported flows.
- [x] Exclude unimplemented behavior from the user guide.
- [x] Confirm that `历史` currently supports viewing details and exported result context, while `设置` persists user preferences.

### Task 2: Write User Guide

**Files:**
- Create: `docs/web-user-guide.md`

- [x] Write a Chinese user guide organized by page:
  - quick start and scene selection
  - `纯人声评测`
  - `综合音频分析`
  - result interpretation
  - `历史`
  - `设置`
  - common usage decisions and limitations
- [x] Keep wording user-facing rather than implementation-facing.
- [x] Ensure all behavior descriptions match current runtime.
- [x] Keep final delivery scope to Chinese only; do not add an English companion document.

### Task 3: Expose Guide in README

**Files:**
- Modify: `README.md`

- [x] Add a minimal `Documentation` section or equivalent entry.
- [x] Include only one link: `docs/web-user-guide.md`.
- [x] Keep existing README structure intact.

### Task 4: Self-Check

**Files:**
- Review: `docs/web-user-guide.md`
- Review: `README.md`

- [x] Verify headings, link path, and terminology consistency.
- [x] Verify the guide does not promise mobile support, batch UI flow, history export from the list page, or history re-analysis.
