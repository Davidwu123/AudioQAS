from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MIN_FFMPEG_VERSION = (6, 0, 0)
MIN_PYTHON_VERSION = (3, 10, 0)


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


def parse_ffmpeg_version(text: str) -> tuple[int, int, int]:
    match = re.search(r"ffmpeg version\s+(\d+)(?:\.(\d+))?(?:\.(\d+))?", text)
    if not match:
        return (0, 0, 0)
    return tuple(int(part or 0) for part in match.groups())


def ffmpeg_version_supported(version: tuple[int, int, int]) -> bool:
    return version >= MIN_FFMPEG_VERSION


def parse_python_version(text: str) -> tuple[int, int, int]:
    match = re.search(r"(?:Python\s+)?(\d+)\.(\d+)(?:\.(\d+))?", text)
    if not match:
        return (0, 0, 0)
    return tuple(int(part or 0) for part in match.groups())


def python_version_supported(version: tuple[int, int, int]) -> bool:
    return version >= MIN_PYTHON_VERSION


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


def log(message: str) -> None:
    print(message, flush=True)


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=check)


def get_python_version(python_bin: str) -> tuple[int, int, int]:
    result = subprocess.run(
        [
            python_bin,
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return parse_python_version((result.stdout or "") + (result.stderr or ""))


def ensure_python() -> str:
    if sys.version_info >= (3, 10):
        return sys.executable
    for name in ("python3.12", "python3.11", "python3.10", "python3"):
        candidate = shutil.which(name)
        if candidate and python_version_supported(get_python_version(candidate)):
            return candidate
    install_python()
    for name in ("python3.12", "python3.11", "python3.10", "python3"):
        candidate = shutil.which(name)
        if candidate and python_version_supported(get_python_version(candidate)):
            return candidate
    raise RuntimeError("Python 3.10+ is required but was not found.")


def install_python() -> None:
    log("[python] Python 3.10+ not found. Automatic install is required.")
    system = platform.system().lower()
    if system == "darwin":
        run_command(["brew", "install", "python@3.12"])
        return
    if system == "linux" and Path("/etc/debian_version").exists():
        run_command(["sudo", "apt-get", "update"])
        run_command(["sudo", "apt-get", "install", "-y", "python3", "python3-venv"])
        return
    raise RuntimeError("Unsupported OS for automatic Python install. Install Python 3.10+ manually.")


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
        version = get_python_version(str(venv_python(root)))
        if not python_version_supported(version):
            log("[python] Existing .venv uses unsupported Python; upgrading in place.")
            run_command([python_bin, "-m", "venv", "--upgrade", ".venv"], cwd=root)
            return
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
    if check_ffmpeg(root):
        return
    install_ffmpeg(root)


def check_ffmpeg(root: Path) -> bool:
    repo_bin = repo_ffmpeg_bin(root).parent
    ffmpeg = find_executable("ffmpeg", [repo_bin])
    ffprobe = find_executable("ffprobe", [repo_bin])
    if ffmpeg and ffprobe:
        version = parse_ffmpeg_version(read_command_output([ffmpeg, "-version"]))
        probe_version = parse_ffmpeg_version(read_command_output([ffprobe, "-version"]).replace("ffprobe", "ffmpeg", 1))
        if ffmpeg_version_supported(version) and ffmpeg_version_supported(probe_version):
            log(f"[ffmpeg] Found supported ffmpeg {version[0]}.{version[1]}.{version[2]}, reuse: {ffmpeg}")
            log(f"[ffmpeg] Found supported ffprobe {probe_version[0]}.{probe_version[1]}.{probe_version[2]}, reuse: {ffprobe}")
            return True
    return False


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
        if not check_ffmpeg(root):
            raise RuntimeError("ffmpeg/ffprobe 6.0+ is required but was not found.")
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


def nisqa_weights_path(root: Path) -> Path:
    return root / "audioqas" / "models" / "weights" / "nisqa.tar"


def smoke_audio_path(root: Path) -> Path:
    return root / ".tmp" / "bootstrap_smoke.wav"


def create_smoke_audio(root: Path) -> Path:
    import math
    import struct
    import wave

    wav_path = smoke_audio_path(root)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 16000
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for i in range(sample_rate * 3):
            value = int(0.1 * 32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
            wav.writeframes(struct.pack("<h", value))
    return wav_path


def warm_dnsmos(wav_path: Path) -> None:
    log("[DNSMOS] Purpose: pure speech quality evaluation for 纯人声评测.")
    from audioqas.models.dnsmos import DNSMOSScorer

    DNSMOSScorer().score(str(wav_path))


def warm_nisqa(root: Path, wav_path: Path) -> None:
    log("[NISQA] Purpose: multi-dimensional speech quality evaluation for 纯人声评测.")
    weights = nisqa_weights_path(root)
    if not weights.exists():
        raise RuntimeError(f"NISQA weights missing: {weights}")
    from audioqas.models.nisqa import NISQAScorer

    NISQAScorer().score(str(wav_path))


def warm_audiobox(wav_path: Path) -> None:
    log("[AudioBox] Purpose: mixed-content analysis for 综合音频分析.")
    try:
        from audioqas.models.audiobox_aesthetics import AudioBoxAestheticsScorer

        AudioBoxAestheticsScorer().score(str(wav_path))
    except Exception as exc:
        raise RuntimeError(
            "AudioBox 模型资产缺失，且无法从 Hugging Face 下载。请恢复网络后重试，或手动提供本地 checkpoint。"
        ) from exc


def internal_warm_models(root: Path) -> None:
    wav_path = create_smoke_audio(root)
    warm_dnsmos(wav_path)
    warm_nisqa(root, wav_path)
    warm_audiobox(wav_path)


def main(argv: list[str] | None = None) -> None:
    effective_argv = sys.argv[1:] if argv is None else argv
    if "--internal-warm-models" in effective_argv:
        internal_warm_models(Path.cwd())
        return
    options = parse_args(effective_argv)
    execute(Path.cwd(), options)


if __name__ == "__main__":
    main()
