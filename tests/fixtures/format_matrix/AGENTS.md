# AGENTS.md

## Scope

This directory stores reusable media fixtures for AudioQAS format-regression tests.

## Fixture Rules

- Keep one canonical fixture per product-promised extension.
- Use the filename pattern `format_matrix.<ext>`.
- Keep fixtures short and deterministic; default duration is `0.35s`.
- Generate fixtures with local `ffmpeg` only. Do not hand-edit binary media.
- Do not place temporary outputs, failed encodes, or large customer files here.
- If a supported extension changes, update:
  - this directory
  - `tests/python/test_web_api.py`
  - `meta/format-support-test-report-2026-05-25.md`

## Current Matrix

- Audio: `wav`, `flac`, `mp3`, `aac`, `m4a`, `ogg`
- Video: `mp4`, `mov`, `mkv`, `avi`
