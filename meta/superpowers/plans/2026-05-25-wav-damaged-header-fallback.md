# WAV Damaged Header Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support RTC dump WAV files whose RIFF/data size fields are wrong but whose PCM payload and format metadata are still recoverable.

**Architecture:** Keep recovery in `audioqas/core/preprocessor.py` as a shared read helper used by all model preprocessors. The helper first uses `soundfile.read()` and only enables fallback for `.wav` files that decode to zero frames while still containing a valid PCM `fmt ` chunk and payload bytes after a `data` chunk.

**Tech Stack:** Python, NumPy, soundfile, pytest, existing AudioQAS preprocessing pipeline.

---

### Task 1: Add Failing Tests For Damaged WAV Header Recovery

**Files:**
- Modify: `tests/python/test_models.py`
- Modify: `tests/python/test_web_api.py`

- [x] **Step 1: Add core recovery tests**

Add tests that build a WAV file with valid PCM metadata, `RIFF`/`data` size set to zero, and real PCM payload after the `data` chunk. Assert the shared reader restores samples and keeps header-only files rejected.

- [x] **Step 2: Add upload API behavior test**

Add a real upload test that uses the damaged header WAV and verifies it reaches the evaluation service instead of returning `empty_audio`.

- [x] **Step 3: Run focused tests to verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_models.py::test_read_audio_recovers_wav_with_zero_data_size_and_pcm_payload tests/python/test_web_api.py::test_upload_damaged_wav_header_with_pcm_payload_reaches_evaluation -q
```

Expected: fail because `read_audio` does not exist and/or the upload path still treats the file as empty.

### Task 2: Implement Shared WAV Recovery Helper

**Files:**
- Modify: `audioqas/core/preprocessor.py`
- Modify: `audioqas/core/__init__.py`

- [x] **Step 1: Implement `read_audio()`**

Create a helper that returns `(audio, sample_rate)`, calls `sf.read()` first, and only falls back when `.wav` decodes to zero samples. The fallback must parse PCM `fmt ` metadata, locate `data`, infer payload length from file size when the declared data size is zero, and convert `uint8`, `int16`, `int24`, or `int32` PCM to float arrays.

- [x] **Step 2: Export helper**

Expose `read_audio` from `audioqas.core.__init__`.

- [x] **Step 3: Run focused tests to verify GREEN**

Run the focused command from Task 1 and confirm it passes.

### Task 3: Route Model Preprocessors Through Shared Reader

**Files:**
- Modify: `audioqas/models/dnsmos.py`
- Modify: `audioqas/models/nisqa.py`
- Modify: `audioqas/models/audiobox_aesthetics.py`
- Modify: `audioqas/models/analysis.py`

- [x] **Step 1: Replace direct `sf.read()` calls**

Use `read_audio()` in all four preprocessing functions so the fallback applies consistently to DNSMOS, NISQA, AudioBox, and signal analysis.

- [x] **Step 2: Run model/API tests**

Run:

```bash
.venv/bin/python -m pytest tests/python/test_models.py tests/python/test_web_api.py -q
```

Expected: all selected tests pass.

### Task 4: Align Format Support Messaging And Plan

**Files:**
- Modify: `audioqas/web/static/web-preview.html`
- Modify: `audioqas/web/static/web-preview-app.js`
- Modify: `docs/web-product-spec.md`
- Modify: `meta/todo.md`
- Modify: `tests/web/web_preview_data.test.mjs`

- [x] **Step 1: Make confirmed support conservative**

Change upload hints to confirmed formats only: `音频 wav/flac/ogg · 视频 mp4/mov/mkv/avi（需 ffmpeg）`.

- [x] **Step 2: Record planned support**

Document `mp3/aac/m4a` as planned ffmpeg-backed audio decode support, and keep `wmv/flv` as backend-detected but not product-promised until fixtures and browser acceptance are added.

- [x] **Step 3: Run web preview tests**

Run:

```bash
npm run test:web-preview
```

Expected: web preview tests pass.

### Task 5: Full Verification

**Files:**
- No new source edits unless verification exposes a real issue.

- [x] **Step 1: Run project verification**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
npm run test:web-preview
```

Expected: all tests pass.
