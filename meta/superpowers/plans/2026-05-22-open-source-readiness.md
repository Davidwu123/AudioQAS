# Open Source Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current AudioQAS repository from a locally optimized development workspace into a clean open-source project that external users can clone, install, run, and understand without relying on internal context.

**Architecture:** Keep the current web runtime and test behavior intact while separating three concerns that are currently mixed together: public product/runtime assets, public developer documentation, and internal AI/project workflow artifacts. Execute in phases: first define the public repo shape and supported flows, then normalize install/start/test entry points, then move or down-rank internal materials, then clean runtime artifacts and verify the final repository can be used from scratch.

**Tech Stack:** Python/FastAPI, Vanilla JS, Playwright, jsdom/node tests, pytest, repo-structure/documentation cleanup

---

## Scope Snapshot

**Current strengths**
- Core web runtime is working locally
- jsdom and Playwright coverage already exists
- Runtime artifact directories are already gitignored
- The repository has a coherent Python package root under `audioqas/`

**Current open-source gaps**
- Public vs internal files are mixed at the repo root
- Runtime frontend assets live under `design/`, which reads like mock/design-only content
- `docs/` mixes public product docs with internal AI planning docs
- Install/start/test instructions are incomplete for first-time external users
- Packaging metadata and public repo basics are incomplete
- Root directory still exposes internal workflow files that are not part of the product
- Legacy runtime copies under `design/web-preview*` may remain temporarily after migration and must be explicitly removed once all references are updated
- Detailed design rules must ultimately live under `docs/`, while `design/` should contain design assets only

---

## Phase 1: Define Public Repository Shape

**Files:**
- Modify: `README.md`
- Modify: `docs/web-product-spec.md`
- Modify: `docs/design-system-detailed.md`
- Modify: `AGENTS.md`
- Add/Modify: `meta/superpowers/plans/2026-05-22-open-source-readiness.md`

- [ ] **Step 1: Decide and document the public root-level contract**

Target:
- Define which root files are public-facing and must remain visible
- Define which files are internal-only and should be moved, hidden from main README flow, or removed later

Minimum public root contract:
- `README.md`
- `LICENSE`
- Python package/project metadata
- `package.json`
- `audioqas/`
- `docs/`
- `tests/`

- [ ] **Step 2: Decide the final directory responsibility model**

Required decisions:
- public runtime frontend assets location
- public design docs location
- internal workflow docs location
- public test layout convention

- [ ] **Step 3: Record the target directory map in this plan before moving files**

Expected output:
- one explicit target tree
- one list of files to move
- one list of files to down-rank instead of move

---

## Phase 2: Normalize Install / Run / Verify Entry Points

**Files:**
- Modify: `README.md`
- Modify: `package.json`
- Modify: `requirements.txt`
- Add: `pyproject.toml`
- Add: `LICENSE`
- Add: optional bootstrap helper such as `scripts/bootstrap.sh` or `Makefile`

- [ ] **Step 1: Add public project metadata**

Required:
- Python project metadata via `pyproject.toml`
- explicit Python version support
- explicit project name/version/entry metadata
- open-source license file

- [ ] **Step 2: Make first-time setup deterministic**

Required docs or scripts:
- Python dependency install
- Node dependency install
- Playwright browser install
- minimal run command
- full verification command set

- [ ] **Step 3: Make public commands readable and stable**

Target:
- `npm run test:web-preview`
- `npm run test:e2e`
- one documented Python run command
- optional one-command bootstrap

- [ ] **Step 4: Document dependency caveats honestly**

Required:
- large model/runtime dependencies
- platform assumptions
- likely slow installs
- optional vs required features

---

## Phase 3: Move Runtime Frontend Assets Out Of `design/`

**Files:**
- Move/Modify: `audioqas/web/static/web-preview.html`
- Move/Modify: `audioqas/web/static/web-preview-data.js`
- Move/Modify: `audioqas/web/static/web-preview-app.js`
- Modify: `audioqas/web/api.py`
- Modify: tests that reference current frontend asset paths
- Modify: `README.md`
- Modify: `docs/web-product-spec.md`

- [ ] **Step 1: Create the public runtime frontend destination**

Recommended target:
- `audioqas/web/static/`
or
- `frontend/`

- [ ] **Step 2: Move runtime HTML/JS assets without changing behavior**

Required:
- keep static serving working
- keep preview page route working
- update any tests and route assumptions

- [ ] **Step 3: Leave `design/` only for design-system artifacts or remove it entirely**

Target:
- runtime assets no longer live in a directory whose name suggests mockups only
- if compatibility copies remain under `design/web-preview*`, record them as temporary legacy files and remove them in a later cleanup step instead of leaving them undocumented

- [ ] **Step 4: Verify**

Run:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
npm run test:web-preview
npm run test:e2e
```

Expected:
- no runtime path regressions
- docs no longer point users at a misleading `design/` runtime location

---

## Phase 4: Separate Public Docs From Internal Workflow Docs

**Files:**
- Move: `meta/superpowers/**`
- Move/Modify: `meta/todo.md`
- Move/Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/web-product-spec.md`
- Modify: `docs/design-system-detailed.md`

- [ ] **Step 1: Decide the internal-doc destination**

Recommended options:
- `meta/`
- `internal/`
- `.project/` only if intentionally hidden from public repo navigation

- [ ] **Step 2: Move AI planning/spec files out of public docs flow**

Target:
- `docs/` only contains public-facing documentation
- internal plans/specs stop competing with public docs
- all remaining `meta/superpowers/*` path references are treated as internal-workflow residue until that move is complete

- [ ] **Step 3: Down-rank or relocate `AGENTS.md` and `todo.md`**

Target:
- root directory no longer looks like an AI workflow workspace first
- public repo identity is centered on the product/project

- [ ] **Step 4: Rewrite README links so public users never need internal docs**

Expected:
- a new user can follow README without touching internal workflow materials

---

## Phase 5: Rework Public Documentation For External Users

**Files:**
- Modify: `README.md`
- Modify: `docs/web-product-spec.md`
- Modify: `docs/web-acceptance-checklist.md`
- Modify: design-system doc destination after Phase 3

- [ ] **Step 1: Rewrite README as a public entry document**

README must answer:
- what this repo is
- what works today
- how to install
- how to run
- how to test
- what is intentionally out of scope

- [ ] **Step 2: Remove internal or historical framing from public docs**

Examples to remove or reduce:
- repeated “old desktop app” cleanup narration
- internal-team-only framing unless intentionally kept as project positioning
- internal workflow references

- [ ] **Step 3: Clarify public product boundaries**

Required:
- supported pages
- supported models
- PC-browser-only constraint if it remains true
- what “history” and “settings” mean in the open-source version

- [ ] **Step 4: Add a “from clone to first run” quickstart**

Target:
- a fresh user can reach the running app and both test suites without guessing

---

## Phase 6: Clean Local-Only Artifacts And Repository Noise

**Files/Dirs:**
- Remove local-only artifacts from workspace as approved
- Modify: `.gitignore`
- Optional: add helper cleanup script

- [ ] **Step 1: Audit local-only artifacts**

Classify:
- safe-to-delete runtime/test caches
- rebuildable dependency directories
- internal tool caches

- [ ] **Step 2: Remove pure local garbage from the working tree**

Examples:
- `.worktrees/`
- `.pytest_cache/`
- `.tmp/test-results/`
- `.tmp/log/`
- `__pycache__/`
- `*.pyc`
- `.DS_Store`
- transient `.tmp` subdirectories as appropriate

- [ ] **Step 3: Decide whether rebuildable environments should remain locally**

Examples:
- `.venv/`
- `node_modules/`

Rule:
- not part of the repository
- may remain locally only if immediately needed for development

- [ ] **Step 4: Verify `.gitignore` matches the cleaned workspace**

Expected:
- no accidental runtime/test noise shows up after normal development commands

---

## Phase 7: Optional Test Layout Cleanup

**Files:**
- Move/Modify: `tests/**`
- Modify: `package.json`
- Modify: pytest/node/playwright references
- Modify: README docs

- [ ] **Step 1: Decide whether to keep mixed test layout or normalize it**

Recommended normalized shape:
```text
tests/
  python/
  web/
  e2e/
  fixtures/
```

- [ ] **Step 2: If normalized, move files with minimal behavior change**

Required:
- Python tests still discoverable
- Node tests still runnable
- Playwright still runnable

- [ ] **Step 3: Update all commands and docs**

Expected:
- test directories communicate intent immediately to external contributors

---

## Phase 8: Final Open-Source Verification

**Files:**
- Modify as needed across repo based on verification results

- [ ] **Step 1: Verify fresh-setup workflow from docs**

Run the documented public flow in order:
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm install
npx playwright install
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
npm run test:web-preview
npm run test:e2e
.venv/bin/python -m audioqas.web.run_local
```

- [ ] **Step 2: Verify repo root is understandable without internal context**

Checklist:
- public entry files are obvious
- no misleading runtime/design/doc naming remains
- no internal-only materials dominate the root or `docs/`

- [ ] **Step 3: Verify no local/private artifacts remain tracked**

Checklist:
- no machine-specific caches
- no runtime logs
- no transient upload/state outputs
- no private tokens or secrets

- [ ] **Step 4: Verify final public narrative**

Checklist:
- repository purpose is clear
- install path is clear
- test path is clear
- supported scope is clear

---

## Final Verification Checklist

- [ ] Public root structure is clean and intentional
- [ ] Runtime frontend assets are no longer misclassified under `design/`
- [ ] No undocumented legacy runtime copies remain under `design/web-preview*`
- [ ] `docs/` contains public docs only
- [ ] Internal AI/project workflow materials are relocated or down-ranked
- [x] Detailed design rules live under `docs/`, while `design/` contains design assets only
- [ ] README supports true first-time clone to first run
- [ ] Python packaging metadata exists
- [ ] License exists
- [ ] Local-only garbage is cleaned or intentionally retained only as local state
- [ ] Both automated test stacks pass from the documented workflow
- [ ] The repository reads as an open-source project, not a private working notebook
