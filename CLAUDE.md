# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Run & Verify

```bash
# Run app
/opt/homebrew/bin/python3.12 -m audioqas.app

# Run all tests
/opt/homebrew/bin/python3.12 -m pytest tests/

# Run single test
/opt/homebrew/bin/python3.12 -m pytest tests/test_models.py -k dnsmos

# Install dependencies
/opt/homebrew/bin/pip3.12 install -r requirements.txt
```

Python 3.12 is at `/opt/homebrew/bin/python3.12` (system default python3 is 3.7, don't use it).

## Architecture

Two evaluation categories, each with its own page and model selector:

1. **Voice evaluation** (语音评测) — MOS scoring for speech quality
   - Models: DNSMOS (16kHz, 3 dims: OVRL/SIG/BAK), NISQA (48kHz, 5 dims: OVRL/NOI/DIS/COL/LOUD)
   - Uses `ScoringManager` to dispatch to active voice model
   - Sidebar shows voice models only when eval page is active

2. **Audio analysis** (音频分析) — music/general audio quality
   - AI scoring: AudioBox-Aesthetics (1-10 scale, 4 dims: PQ/CE/CU/PC)
   - Signal metrics: AudioAnalyzer (LUFS/LRA/TruePeak/Clipping/THD) — independent class, not BaseScorer
   - `AnalysisWorker` runs both AES scoring and signal analysis in sequence
   - Sidebar shows audio models only when analysis page is active

### Key patterns

- **BaseScorer** (`models/base.py`): All MOS scorers implement this ABC with `name`, `version`, `dimensions`, `score()` properties. Returns `ScoreResult` TypedDict.
- **DimensionRegistry** (`core/dimensions.py`): Each model registers its Chinese labels, descriptions, and metaphors at import time. UI queries dynamically instead of hardcoding.
- **Preprocessing**: Each model module has its own `_preprocess_audio()` / `_preprocess_for_aes()` / `_preprocess_for_nisqa()` because target SR differs (DNSMOS=16kHz, NISQA=48kHz, AudioBox/AudioAnalyzer=keep original SR). Video files are extracted via ffmpeg first. Preprocessed files go to `~/Library/Application Support/AudioQAS/preprocessed/`.
- **Theme system**: Colors and typography come from `design/design-tokens.json`. `ui/theme.py` loads tokens and generates QSS. Never hardcode colors in UI code — use `_color(t, "text", "primary")` etc.
- **Workers**: `ScoringWorker` and `AnalysisWorker` are QThread subclasses that emit progress signals back to MainWindow. This keeps UI responsive during model inference.

### Adding a new model

1. Create `models/xxx.py` with a class inheriting `BaseScorer`
2. Register dimension metadata via `DimensionRegistry.register()` at module level
3. Add preprocessing logic (resample to target SR, mono conversion)
4. Register in `MainWindow.__init__()` and add to `MODELS` or `ANALYSIS_MODELS` list in `sidebar.py`
5. If dimensions differ from existing models, ScoreCardWidget rebuilds dynamically

## Design tokens

`design/design-tokens.json` is the single source for all visual constants. Structure:

```
color.base.background, color.accent.primary, color.score.excellent...
typography.fontSize.xs/sm/md/lg/xl
borderRadius.sm/md/lg
```

`design/design-preview.html` renders a visual preview of all tokens.

## Data storage

- History DB: `~/Library/Application Support/AudioQAS/history.db` (SQLite, managed by `HistoryManager`)
- Preprocessed files: `~/Library/Application Support/AudioQAS/preprocessed/`
- NISQA weights: `audioqas/models/weights/nisqa.tar`

## Constraints

- QSS styles must come from design tokens, not hardcoded
- Score results must include `model_name` and `model_version`
- AudioAnalyzer is NOT a BaseScorer — it has its own `AnalysisResult` TypedDict
- NISQA may fail to import (wrapped in try/except in MainWindow init)
- AudioBox-Aesthetics forces CPU on macOS (MPS doesn't support autocast)