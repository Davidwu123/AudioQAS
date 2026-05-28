# FFmpeg Format Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify AudioQAS input-format support with ffmpeg-generated real media files and align product support copy with measured behavior.

**Architecture:** Add pytest integration coverage that generates temporary audio/video fixtures via the local `ffmpeg`, uploads them through the API, and uses a lightweight evaluation service that runs the real preprocessing path without expensive model inference. Add ffmpeg-backed compressed audio decoding for `mp3/aac/m4a` so these formats become tested product support rather than only planned support.

**Tech Stack:** Python, pytest, FastAPI TestClient, ffmpeg, NumPy, soundfile, existing AudioQAS preprocessing utilities.

---

### Task 1: Add RED Format Matrix Test

**Files:**
- Modify: `tests/python/test_web_api.py`

- [x] **Step 1: Add ffmpeg fixture generation helpers**

Generate temporary files for `wav/flac/ogg/mp3/aac/m4a/mp4/mov/mkv/avi` using `ffmpeg` lavfi sine and testsrc sources.

- [x] **Step 2: Add upload + preprocess matrix test**

For each generated file, upload through `/api/evaluate/upload` and use a lightweight evaluation service that calls the real DNSMOS preprocessing function.

- [x] **Step 3: Run focused test and observe RED**

Expected: compressed audio entries fail before ffmpeg-backed audio decode is implemented.

### Task 2: Implement FFmpeg-Backed Compressed Audio Decode

**Files:**
- Modify: `audioqas/core/preprocessor.py`
- Modify: `audioqas/models/dnsmos.py`
- Modify: `audioqas/models/nisqa.py`
- Modify: `audioqas/models/audiobox_aesthetics.py`
- Modify: `audioqas/models/analysis.py`

- [x] **Step 1: Add compressed audio extension set and decode helper**

Support `mp3/aac/m4a` by decoding to mono WAV through ffmpeg.

- [x] **Step 2: Route model preprocessors through the decode helper**

Apply the same decode behavior consistently across all four model preprocessors.

- [x] **Step 3: Run focused matrix test and observe GREEN**

Expected: all generated formats in the matrix upload and preprocess successfully.

### Task 3: Align Product Copy And Docs

**Files:**
- Modify: `audioqas/web/static/web-preview.html`
- Modify: `audioqas/web/static/web-preview-app.js`
- Modify: `docs/web-product-spec.md`
- Modify: `meta/todo.md`
- Modify: `tests/web/web_preview_data.test.mjs`

- [x] **Step 1: Move `mp3/aac/m4a` from planned support to confirmed support**

Update UI hint and product spec to reflect measured support.

- [x] **Step 2: Keep `wmv/flv` out of product promise**

They remain backend-recognized video extensions but are not covered by the requested product format matrix.

### Task 4: Verification And Report

**Files:**
- Add: `meta/format-support-test-report-2026-05-25.md`

- [x] **Step 1: Run focused matrix test**

Command:

```bash
.venv/bin/python -m pytest tests/python/test_web_api.py::test_product_format_fixtures_upload_and_preprocess -q
```

- [x] **Step 2: Run project verification**

Commands:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
npm run test:web-preview
```

- [x] **Step 3: Write test report**

Summarize generated formats, codec/container choices, preprocessing result, and remaining non-promised formats.
