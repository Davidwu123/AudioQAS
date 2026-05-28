# AudioQAS One-Click Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Implement `meta/superpowers/specs/2026-05-28-one-click-bootstrap-design.md`: one command clones AudioQAS, prepares runtime dependencies and model assets, starts the local web service, and opens the browser; test dependencies install only with `--with-test`.

**Architecture:** Keep `scripts/audioqas-install.sh` as a small `curl | bash` thin installer that only handles `git`, clone/update, target directory protection, and delegation. Put bootstrap decisions in `audioqas/bootstrap.py` so install scope, ffmpeg/model checks, idempotency, and command composition are testable without mutating the host machine. Keep `scripts/audioqas-bootstrap` as a tiny repository entry point into `.venv`/Python.

**Tech Stack:** Bash, Python 3.10+, `venv`, `pip`, ffmpeg/ffprobe, FastAPI runtime, pytest, Node/npm/Playwright only under `--with-test`.

---

## File Map

- Create: `audioqas/bootstrap.py`
  - Python implementation of `./scripts/audioqas-bootstrap`.
  - Handles argument parsing, environment probing, `.venv` creation, runtime/dev package install, ffmpeg reuse/install strategy, model smoke checks, service launch, and browser open.
  - Exposes small pure helpers for unit tests: version parsing, repo-local tool path resolution, command planning, model cache environment.
- Create: `scripts/audioqas-bootstrap`
  - Executable shell entry point.
  - Finds a Python 3.10+ interpreter, creates `.venv` if missing enough to run `audioqas.bootstrap`, then delegates into `.venv/bin/python -m audioqas.bootstrap`.
- Create: `scripts/audioqas-install.sh`
  - Executable `curl | bash` thin installer.
  - Parses `--dir`, `--with-test`, `--check-only`, clones or updates `Davidwu123/AudioQAS`, protects non-AudioQAS directories, then invokes `./scripts/audioqas-bootstrap`.
- Create: `tests/python/test_bootstrap.py`
  - Unit tests for bootstrap parser/planner/helpers and dry-run behavior.
  - Verifies default mode skips pytest/Node/npm/Playwright and `--with-test` includes them.
  - Verifies `.venv` model cache env and ffmpeg version policy.
- Create: `tests/shell/test_audioqas_install.sh`
  - Shell regression test for thin installer using stub `git`, `brew`, and `apt-get` in temp dirs.
  - Verifies default current-directory target rules and overwrite protection.
- Modify: `tests/python/test_web_service.py`
  - Add a lightweight assertion that bootstrap script paths exist and are executable.
- Modify: `pyproject.toml`
  - Ensure `audioqas.bootstrap` can be imported through editable install.
  - Keep default runtime deps unchanged; pytest remains only in `[project.optional-dependencies].dev`.
- Modify: `README.md`
  - Replace manual-first setup with repository URL plus one-click install command.
  - Explain `github.com/...` vs `raw.githubusercontent.com/...`.
  - Document existing repo command and `--with-test`.
- Modify: `CONTRIBUTING.md`
  - Use `./scripts/audioqas-bootstrap --with-test` for developer setup.
  - List exact test commands after setup.
- Modify: `AGENTS.md`
  - Align Run & Verify with the new scripts and default/test install split.

## Task 1: Bootstrap Planner And Default Scope

**Files:**
- Create: `audioqas/bootstrap.py`
- Create: `tests/python/test_bootstrap.py`

- [x] **Step 1: Write failing parser/default-scope tests**

Add tests that call pure functions only:

```python
from pathlib import Path

from audioqas import bootstrap


def test_default_options_skip_test_toolchain(tmp_path):
    options = bootstrap.parse_args([])
    plan = bootstrap.build_plan(tmp_path, options)

    assert plan.with_test is False
    assert plan.install_pytest is False
    assert plan.install_node is False
    assert plan.install_playwright is False
    assert plan.python_install_target == "."


def test_with_test_options_include_test_toolchain(tmp_path):
    options = bootstrap.parse_args(["--with-test"])
    plan = bootstrap.build_plan(tmp_path, options)

    assert plan.with_test is True
    assert plan.install_pytest is True
    assert plan.install_node is True
    assert plan.install_playwright is True
    assert plan.python_install_target == ".[dev]"


def test_model_cache_environment_is_repo_local(tmp_path):
    env = bootstrap.model_cache_env(tmp_path)

    assert env["HF_HOME"] == str(tmp_path / ".venv" / "model-cache" / "huggingface")
    assert env["TORCH_HOME"] == str(tmp_path / ".venv" / "model-cache" / "torch")
    assert env["XDG_CACHE_HOME"] == str(tmp_path / ".venv" / "cache")
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_bootstrap.py -q
```

Expected: fail because `audioqas.bootstrap` does not exist.

- [x] **Step 3: Implement minimal planner**

Create `audioqas/bootstrap.py` with:

```python
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BootstrapOptions:
    with_test: bool = False
    check_only: bool = False
    no_start: bool = False
    no_open: bool = False
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass(frozen=True)
class BootstrapPlan:
    root: Path
    with_test: bool
    install_pytest: bool
    install_node: bool
    install_playwright: bool
    python_install_target: str


def parse_args(argv: list[str] | None = None) -> BootstrapOptions:
    parser = argparse.ArgumentParser(description="Prepare and launch AudioQAS locally.")
    parser.add_argument("--with-test", action="store_true", help="Install pytest, npm packages, and Playwright.")
    parser.add_argument("--check-only", action="store_true", help="Only probe dependencies; do not install or start.")
    parser.add_argument("--no-start", action="store_true", help="Prepare environment but do not start the web service.")
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser after starting.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    return BootstrapOptions(
        with_test=args.with_test,
        check_only=args.check_only,
        no_start=args.no_start,
        no_open=args.no_open,
        host=args.host,
        port=args.port,
    )


def build_plan(root: Path, options: BootstrapOptions) -> BootstrapPlan:
    return BootstrapPlan(
        root=root,
        with_test=options.with_test,
        install_pytest=options.with_test,
        install_node=options.with_test,
        install_playwright=options.with_test,
        python_install_target=".[dev]" if options.with_test else ".",
    )


def model_cache_env(root: Path) -> dict[str, str]:
    venv = root / ".venv"
    return {
        "HF_HOME": str(venv / "model-cache" / "huggingface"),
        "TORCH_HOME": str(venv / "model-cache" / "torch"),
        "XDG_CACHE_HOME": str(venv / "cache"),
    }
```

- [x] **Step 4: Run tests and verify GREEN**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_bootstrap.py -q
```

Expected: pass.

## Task 2: ffmpeg Reuse And Version Policy

**Files:**
- Modify: `audioqas/bootstrap.py`
- Modify: `tests/python/test_bootstrap.py`

- [x] **Step 1: Write failing ffmpeg tests**

Add:

```python
def test_parse_ffmpeg_version():
    assert bootstrap.parse_ffmpeg_version("ffmpeg version 7.1.1 Copyright") == (7, 1, 1)
    assert bootstrap.parse_ffmpeg_version("ffmpeg version 6.0") == (6, 0, 0)
    assert bootstrap.parse_ffmpeg_version("not ffmpeg") == (0, 0, 0)


def test_ffmpeg_version_requires_six_or_newer():
    assert bootstrap.ffmpeg_version_supported((6, 0, 0)) is True
    assert bootstrap.ffmpeg_version_supported((7, 1, 1)) is True
    assert bootstrap.ffmpeg_version_supported((5, 1, 0)) is False
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_bootstrap.py -q
```

Expected: fail because version helpers do not exist.

- [x] **Step 3: Implement version helpers and ffmpeg path helpers**

Add:

```python
import re
import shutil
import subprocess


MIN_FFMPEG_VERSION = (6, 0, 0)


def parse_ffmpeg_version(text: str) -> tuple[int, int, int]:
    match = re.search(r"ffmpeg version\s+(\d+)(?:\.(\d+))?(?:\.(\d+))?", text)
    if not match:
        return (0, 0, 0)
    return tuple(int(part or 0) for part in match.groups())


def ffmpeg_version_supported(version: tuple[int, int, int]) -> bool:
    return version >= MIN_FFMPEG_VERSION


def repo_ffmpeg_bin(root: Path) -> Path:
    return root / ".venv" / "tools" / "ffmpeg" / "bin" / "ffmpeg"


def find_executable(name: str, extra_paths: list[Path] | None = None) -> str | None:
    paths = [str(path) for path in extra_paths or []]
    search_path = ":".join(paths)
    if search_path:
        import os
        search_path = search_path + ":" + os.environ.get("PATH", "")
        return shutil.which(name, path=search_path)
    return shutil.which(name)


def read_command_output(command: list[str]) -> str:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    return (result.stdout or "") + (result.stderr or "")
```

- [x] **Step 4: Run tests and verify GREEN**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_bootstrap.py -q
```

Expected: pass.

## Task 3: Runtime Bootstrap Execution

**Files:**
- Modify: `audioqas/bootstrap.py`
- Modify: `tests/python/test_bootstrap.py`

- [x] **Step 1: Write failing dry-run execution tests**

Add:

```python
class Recorder:
    def __init__(self):
        self.commands = []

    def run(self, command, *, cwd=None, env=None, check=True):
        self.commands.append((list(command), cwd, env, check))


def test_default_bootstrap_commands_do_not_include_node_or_playwright(tmp_path, monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(bootstrap, "run_command", recorder.run)
    monkeypatch.setattr(bootstrap, "ensure_python", lambda: "python3")
    monkeypatch.setattr(bootstrap, "ensure_ffmpeg", lambda root: None)
    monkeypatch.setattr(bootstrap, "warm_models", lambda root, env: None)

    bootstrap.execute(tmp_path, bootstrap.parse_args(["--no-start"]))

    commands = [" ".join(command) for command, *_ in recorder.commands]
    assert any("-m venv .venv" in command for command in commands)
    assert any("-m pip install -e ." in command for command in commands)
    assert not any("npm" in command for command in commands)
    assert not any("playwright" in command for command in commands)


def test_with_test_bootstrap_commands_include_node_and_playwright(tmp_path, monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(bootstrap, "run_command", recorder.run)
    monkeypatch.setattr(bootstrap, "ensure_python", lambda: "python3")
    monkeypatch.setattr(bootstrap, "ensure_ffmpeg", lambda root: None)
    monkeypatch.setattr(bootstrap, "warm_models", lambda root, env: None)
    monkeypatch.setattr(bootstrap, "ensure_node", lambda root: None)

    bootstrap.execute(tmp_path, bootstrap.parse_args(["--with-test", "--no-start"]))

    commands = [" ".join(command) for command, *_ in recorder.commands]
    assert any("-m pip install -e .[dev]" in command for command in commands)
    assert any(command == "npm ci" for command in commands)
    assert any("playwright install chromium" in command for command in commands)
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_bootstrap.py -q
```

Expected: fail because execution helpers do not exist.

- [x] **Step 3: Implement execution skeleton**

Add:

```python
import os
import platform
import subprocess
import sys


def log(message: str) -> None:
    print(message, flush=True)


def run_command(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, check: bool = True) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=check)


def ensure_python() -> str:
    if sys.version_info >= (3, 10):
        return sys.executable
    candidate = shutil.which("python3")
    if candidate is None:
        raise RuntimeError("Python 3.10+ is required but was not found.")
    return candidate


def venv_python(root: Path) -> Path:
    return root / ".venv" / "bin" / "python"


def runtime_env(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(model_cache_env(root))
    ffmpeg_bin = root / ".venv" / "tools" / "ffmpeg" / "bin"
    env["PATH"] = str(ffmpeg_bin) + os.pathsep + env.get("PATH", "")
    return env


def ensure_venv(root: Path, python_bin: str) -> None:
    if venv_python(root).exists():
        log("[python] Reusing .venv")
        return
    log("[python] Purpose: run AudioQAS backend, model inference, and audio processing.")
    log("[python] Install location: .venv")
    run_command([python_bin, "-m", "venv", ".venv"], cwd=root)


def install_python_packages(root: Path, target: str, env: dict[str, str]) -> None:
    python = str(venv_python(root))
    run_command([python, "-m", "pip", "install", "--upgrade", "pip"], cwd=root, env=env)
    run_command([python, "-m", "pip", "install", "-e", target], cwd=root, env=env)


def ensure_ffmpeg(root: Path) -> None:
    log("[ffmpeg] Purpose: decode compressed audio and extract audio from video uploads.")
    log("[ffmpeg] Internal usage: mp3/aac/m4a decode and mp4/mov/mkv/avi audio extraction.")
    found = find_executable("ffmpeg", [repo_ffmpeg_bin(root).parent])
    if found:
        version = parse_ffmpeg_version(read_command_output([found, "-version"]))
        if ffmpeg_version_supported(version):
            log(f"[ffmpeg] Found supported ffmpeg {version[0]}.{version[1]}.{version[2]}, reuse: {found}")
            return
    install_ffmpeg(root)


def install_ffmpeg(root: Path) -> None:
    log("[ffmpeg] Supported ffmpeg not found. Automatic install is required.")
    system = platform.system().lower()
    if system == "darwin":
        run_command(["brew", "install", "ffmpeg"])
        return
    if system == "linux" and Path("/etc/debian_version").exists():
        run_command(["sudo", "apt-get", "update"])
        run_command(["sudo", "apt-get", "install", "-y", "ffmpeg"])
        return
    raise RuntimeError("Unsupported OS for automatic ffmpeg install. Install ffmpeg 6.0+ manually.")


def ensure_node(root: Path) -> None:
    log("[node] Purpose: run jsdom and Playwright tests under --with-test.")
    node = shutil.which("node")
    npm = shutil.which("npm")
    if node and npm:
        log(f"[node] Found system Node/npm, reuse: {node} / {npm}")
        return
    system = platform.system().lower()
    if system == "darwin":
        run_command(["brew", "install", "node"])
        return
    if system == "linux" and Path("/etc/debian_version").exists():
        run_command(["sudo", "apt-get", "update"])
        run_command(["sudo", "apt-get", "install", "-y", "nodejs", "npm"])
        return
    raise RuntimeError("Node.js 18+ and npm are required for --with-test.")


def warm_models(root: Path, env: dict[str, str]) -> None:
    python = str(venv_python(root))
    run_command([python, "-m", "audioqas.bootstrap", "--internal-warm-models"], cwd=root, env=env)


def start_service(root: Path, options: BootstrapOptions, env: dict[str, str]) -> None:
    env = dict(env)
    env["AUDIOQAS_WEB_HOST"] = options.host
    env["AUDIOQAS_WEB_PORT"] = str(options.port)
    run_command([str(venv_python(root)), "-m", "audioqas.web.run_local"], cwd=root, env=env, check=False)


def open_browser(options: BootstrapOptions) -> None:
    if options.no_open:
        return
    url = f"http://{options.host}:{options.port}"
    system = platform.system().lower()
    if system == "darwin":
        subprocess.Popen(["open", url])
    elif system == "linux" and shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", url])
    else:
        log(f"[web] Open this URL manually: {url}")


def execute(root: Path, options: BootstrapOptions) -> None:
    log(f"[system] {platform.system()} {platform.machine()}")
    plan = build_plan(root, options)
    env = runtime_env(root)
    python_bin = ensure_python()
    if options.check_only:
        ensure_ffmpeg(root)
        log("[check] Complete.")
        return
    ensure_venv(root, python_bin)
    install_python_packages(root, plan.python_install_target, env)
    ensure_ffmpeg(root)
    if plan.with_test:
        ensure_node(root)
        run_command(["npm", "ci"], cwd=root, env=env)
        run_command(["npx", "playwright", "install", "chromium"], cwd=root, env=env)
    warm_models(root, env)
    if not options.no_start:
        open_browser(options)
        start_service(root, options, env)
```

- [x] **Step 4: Run tests and verify GREEN**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_bootstrap.py -q
```

Expected: pass.

## Task 4: Model Warm-Up And Asset Checks

**Files:**
- Modify: `audioqas/bootstrap.py`
- Modify: `tests/python/test_bootstrap.py`

- [x] **Step 1: Write failing asset-check tests**

Add:

```python
def test_nisqa_weights_path_exists():
    assert bootstrap.nisqa_weights_path(Path.cwd()).name == "nisqa.tar"


def test_audio_fixture_path_is_under_tmp(tmp_path):
    assert bootstrap.smoke_audio_path(tmp_path) == tmp_path / ".tmp" / "bootstrap_smoke.wav"
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_bootstrap.py -q
```

Expected: fail because helpers do not exist.

- [x] **Step 3: Implement warm-up helpers**

Add:

```python
def nisqa_weights_path(root: Path) -> Path:
    return root / "audioqas" / "models" / "weights" / "nisqa.tar"


def smoke_audio_path(root: Path) -> Path:
    return root / ".tmp" / "bootstrap_smoke.wav"


def internal_warm_models(root: Path) -> None:
    import math
    import wave
    import struct

    wav_path = smoke_audio_path(root)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 16000
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for i in range(sample_rate // 10):
            value = int(0.1 * 32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
            wav.writeframes(struct.pack("<h", value))

    log("[DNSMOS] Purpose: pure speech quality evaluation for 纯人声评测.")
    import speechmos.dnsmos  # noqa: F401

    log("[NISQA] Purpose: multi-dimensional speech quality evaluation for 纯人声评测.")
    weights = nisqa_weights_path(root)
    if not weights.exists():
        raise RuntimeError(f"NISQA weights missing: {weights}")
    from nisqa.NISQA_model import nisqaModel  # noqa: F401

    log("[AudioBox] Purpose: mixed-content analysis for 综合音频分析.")
    try:
        from audiobox_aesthetics.infer import initialize_predictor

        initialize_predictor()
    except Exception as exc:
        raise RuntimeError(
            "AudioBox 模型资产缺失，且无法从 Hugging Face 下载。请恢复网络后重试，或手动提供本地 checkpoint。"
        ) from exc
```

Update `main()`:

```python
def main(argv: list[str] | None = None) -> None:
    if argv and "--internal-warm-models" in argv:
        internal_warm_models(Path.cwd())
        return
    options = parse_args(argv)
    execute(Path.cwd(), options)


if __name__ == "__main__":
    main()
```

- [x] **Step 4: Run tests and verify GREEN**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_bootstrap.py -q
```

Expected: pass.

## Task 5: Repository Bootstrap Shell Entry

**Files:**
- Create: `scripts/audioqas-bootstrap`
- Modify: `tests/python/test_web_service.py`

- [x] **Step 1: Write failing executable test**

Add:

```python
def test_audioqas_bootstrap_script_exists_and_is_executable():
    from pathlib import Path
    import os

    script = Path(__file__).resolve().parents[2] / "scripts" / "audioqas-bootstrap"
    assert script.exists()
    assert os.access(script, os.X_OK)
```

- [x] **Step 2: Run test and verify RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_service.py::test_audioqas_bootstrap_script_exists_and_is_executable -q
```

Expected: fail because script does not exist.

- [x] **Step 3: Create script**

Create executable `scripts/audioqas-bootstrap`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -x ".venv/bin/python" ]; then
  echo "[python] Purpose: create repo-local virtual environment for AudioQAS runtime."
  "$PYTHON_BIN" -m venv .venv
fi

".venv/bin/python" -m audioqas.bootstrap "$@"
```

Run:

```bash
chmod +x scripts/audioqas-bootstrap
```

- [x] **Step 4: Run test and verify GREEN**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_web_service.py::test_audioqas_bootstrap_script_exists_and_is_executable -q
```

Expected: pass.

## Task 6: Thin Installer

**Files:**
- Create: `scripts/audioqas-install.sh`
- Create: `tests/shell/test_audioqas_install.sh`

- [x] **Step 1: Write failing shell installer tests**

Create `tests/shell/test_audioqas_install.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT_DIR/scripts/audioqas-install.sh"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

mkdir -p "$TMP_DIR/bin"
cat >"$TMP_DIR/bin/git" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
echo "git $*" >> "$AUDIOQAS_TEST_LOG"
case "$1" in
  rev-parse)
    if [ "${PWD##*/}" = "AudioQAS" ] && [ -f ".git/audioqas-remote" ]; then
      exit 0
    fi
    exit 1
    ;;
  remote)
    if [ -f ".git/audioqas-remote" ]; then
      cat ".git/audioqas-remote"
      exit 0
    fi
    exit 1
    ;;
  clone)
    target="$3"
    mkdir -p "$target/.git" "$target/scripts"
    echo "https://github.com/Davidwu123/AudioQAS.git" > "$target/.git/audioqas-remote"
    cat > "$target/scripts/audioqas-bootstrap" <<'BOOT'
#!/usr/bin/env bash
echo "bootstrap $*" >> "$AUDIOQAS_TEST_LOG"
BOOT
    chmod +x "$target/scripts/audioqas-bootstrap"
    ;;
  pull)
    ;;
esac
STUB
chmod +x "$TMP_DIR/bin/git"

export AUDIOQAS_TEST_LOG="$TMP_DIR/log"
export PATH="$TMP_DIR/bin:$PATH"

cd "$TMP_DIR"
"$SCRIPT" --with-test --no-start --no-open

grep -q "git clone https://github.com/Davidwu123/AudioQAS.git AudioQAS" "$AUDIOQAS_TEST_LOG" || fail "clone not called"
grep -q "bootstrap --with-test --no-start --no-open" "$AUDIOQAS_TEST_LOG" || fail "bootstrap args not forwarded"

mkdir -p "$TMP_DIR/conflict/AudioQAS"
cd "$TMP_DIR/conflict"
if "$SCRIPT" >/tmp/audioqas-install-conflict.log 2>&1; then
  fail "installer should reject non-repo AudioQAS directory"
fi
grep -q "already exists but is not AudioQAS repo" /tmp/audioqas-install-conflict.log || fail "missing conflict error"
```

- [x] **Step 2: Run test and verify RED**

Run:

```bash
bash tests/shell/test_audioqas_install.sh
```

Expected: fail because installer does not exist.

- [x] **Step 3: Create thin installer**

Create executable `scripts/audioqas-install.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/Davidwu123/AudioQAS.git"
RAW_SCRIPT_URL="https://raw.githubusercontent.com/Davidwu123/AudioQAS/main/scripts/audioqas-install.sh"
TARGET_DIR=""
BOOTSTRAP_ARGS=()

log() {
  printf '%s\n' "$*"
}

install_git_if_missing() {
  if command -v git >/dev/null 2>&1; then
    return
  fi
  log "[git] Purpose: clone or update AudioQAS source code from GitHub."
  if command -v brew >/dev/null 2>&1; then
    brew install git
    return
  fi
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y git
    return
  fi
  log "[git] Failed. Reason: git missing and no supported package manager found."
  exit 1
}

is_audioqas_repo() {
  dir="$1"
  [ -d "$dir/.git" ] || return 1
  (
    cd "$dir"
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 &&
      git remote get-url origin 2>/dev/null | grep -Eq 'github.com[:/]Davidwu123/AudioQAS(\.git)?$'
  )
}

resolve_target_dir() {
  if [ -n "$TARGET_DIR" ]; then
    printf '%s\n' "$TARGET_DIR"
    return
  fi
  if is_audioqas_repo "."; then
    printf '%s\n' "."
    return
  fi
  printf '%s\n' "AudioQAS"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dir)
      shift
      [ "$#" -gt 0 ] || { log "--dir requires a path"; exit 1; }
      TARGET_DIR="$1"
      ;;
    --dir=*)
      TARGET_DIR="${1#--dir=}"
      ;;
    *)
      BOOTSTRAP_ARGS+=("$1")
      ;;
  esac
  shift
done

install_git_if_missing

target="$(resolve_target_dir)"
if [ -e "$target" ]; then
  if ! is_audioqas_repo "$target"; then
    log "[repo] Failed. Reason: $target already exists but is not AudioQAS repo. Next: choose another --dir or move that directory."
    exit 1
  fi
  log "[repo] Found AudioQAS repo at $target, updating."
  (cd "$target" && git pull --ff-only)
else
  log "[repo] Purpose: download AudioQAS source code."
  log "[repo] Source: $REPO_URL"
  git clone "$REPO_URL" "$target"
fi

cd "$target"
exec ./scripts/audioqas-bootstrap "${BOOTSTRAP_ARGS[@]}"
```

Run:

```bash
chmod +x scripts/audioqas-install.sh
```

- [x] **Step 4: Run test and verify GREEN**

Run:

```bash
bash tests/shell/test_audioqas_install.sh
```

Expected: pass.

## Task 7: Docs Alignment

**Files:**
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `AGENTS.md`

- [x] **Step 1: Write failing docs consistency test**

Add to `tests/python/test_bootstrap.py`:

```python
def test_docs_reference_one_click_install_and_with_test():
    root = Path.cwd()
    readme = (root / "README.md").read_text(encoding="utf-8")
    contributing = (root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")

    assert "https://github.com/Davidwu123/AudioQAS" in readme
    assert "raw.githubusercontent.com/Davidwu123/AudioQAS/main/scripts/audioqas-install.sh" in readme
    assert "./scripts/audioqas-bootstrap --with-test" in contributing
    assert "./scripts/audioqas-bootstrap --with-test" in agents
    assert ".venv/bin/python -m pip install pytest" not in agents
```

- [x] **Step 2: Run test and verify RED**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_bootstrap.py::test_docs_reference_one_click_install_and_with_test -q
```

Expected: fail because docs still show the old manual path.

- [x] **Step 3: Update docs**

Update docs so:

- README has repository URL and one-click command:

```bash
curl -fsSL https://raw.githubusercontent.com/Davidwu123/AudioQAS/main/scripts/audioqas-install.sh | bash
```

- README explains `github.com/Davidwu123/AudioQAS` is the human repo page and `raw.githubusercontent.com/...` is the raw script URL for `curl`.
- README existing repo path is:

```bash
./scripts/audioqas-bootstrap
```

- Developer setup is:

```bash
./scripts/audioqas-bootstrap --with-test
```

- CONTRIBUTING and AGENTS use the same commands and state default mode does not install pytest, Node/npm, `node_modules`, or Playwright.

- [x] **Step 4: Run docs test and verify GREEN**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_bootstrap.py::test_docs_reference_one_click_install_and_with_test -q
```

Expected: pass.

## Task 8: Final Verification

**Files:**
- All files above

- [x] **Step 1: Run focused bootstrap tests**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/python/test_bootstrap.py tests/python/test_web_service.py::test_audioqas_bootstrap_script_exists_and_is_executable -q
```

Expected: pass.

- [x] **Step 2: Run shell installer regression**

Run:

```bash
bash tests/shell/test_audioqas_install.sh
```

Expected: pass.

- [x] **Step 3: Run Python suite**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests -q
```

Expected: pass.

- [x] **Step 4: Run web preview tests**

Run:

```bash
npm run test:web-preview
```

Expected: pass.

- [x] **Step 5: Run bootstrap dry checks**

Run:

```bash
./scripts/audioqas-bootstrap --check-only
```

Expected: checks complete without installing test dependencies. If system ffmpeg is missing, failure message must explain purpose, reason, and next step.

Run:

```bash
./scripts/audioqas-bootstrap --with-test --no-start --no-open
```

Expected: runtime/dev setup completes, test toolchain install path is selected, and service is not started.

## Self-Review Notes

- Spec coverage: thin installer, default target dir, repo protection, `.venv`, ffmpeg policy, model env, `--with-test`, docs, and idempotency are covered.
- Red-line handling: implementation contains system install commands, but tests do not execute them on this machine. Running the real script may install global packages only when the user intentionally runs the script.
- Non-goals preserved: no Windows support, no Docker, no daemon, no shell profile edits, no default real backend full E2E.
