"""Shared audio preprocessing utilities for all model scorers."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
import numpy as np

from audioqas.logging import get_logger, set_event


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREPROCESS_DIR = str(PROJECT_ROOT / ".tmp" / "preprocessed")
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"}
logger = get_logger(__name__)
PREPROCESS_SETTINGS = {
    "resample": True,
    "to_mono": True,
    "extract_audio": True,
}


def configure_preprocessor(*, resample: bool, to_mono: bool, extract_audio: bool) -> None:
    PREPROCESS_SETTINGS["resample"] = resample
    PREPROCESS_SETTINGS["to_mono"] = to_mono
    PREPROCESS_SETTINGS["extract_audio"] = extract_audio


def current_preprocess_settings() -> dict[str, bool]:
    return dict(PREPROCESS_SETTINGS)


def format_pipeline_steps(steps: list[str], model_label: str) -> str:
    mapping = {
        "source_video": "原始视频",
        "source_audio": "原始文件",
        "extract_audio": "抽取音轨",
        "to_mono": "转单声道",
        "resample_16k": "重采样到 16kHz",
        "keep_48k": "保持 48kHz",
        "passthrough": "直接使用原始音频",
    }
    labels = [mapping.get(step, step) for step in steps]
    labels.append(f"送入 {model_label}")
    return " → ".join(labels)


def _ensure_preprocess_dir() -> str:
    preprocess_dir = os.environ.get("AUDIOQAS_PREPROCESS_DIR", DEFAULT_PREPROCESS_DIR)
    os.makedirs(preprocess_dir, exist_ok=True)
    return preprocess_dir


def build_preprocessed_name(
    original_path: str,
    *,
    target_sr: int | None = None,
    is_video: bool = False,
) -> str:
    base = os.path.splitext(os.path.basename(original_path))[0]
    parts = [base]
    if is_video:
        parts.append("from_video")
    if target_sr is not None:
        parts.append(f"{target_sr}Hz")
    parts.append("mono")
    return "_".join(parts) + ".wav"


def _extract_audio(video_path: str, target_sr: int, out_name: str | None = None) -> str:
    """Extract audio from video, resample to target_sr, convert to mono WAV."""
    if out_name is None:
        out_name = build_preprocessed_name(video_path, target_sr=target_sr, is_video=True)
    out_path = os.path.join(_ensure_preprocess_dir(), out_name)
    with set_event("branch_selected"):
        logger.info("branch=video_extract file=%s target_sr=%s output=%s", video_path, target_sr, out_path)
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
           "-ar", str(target_sr), "-ac", "1", "-y", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def _to_mono(audio: np.ndarray) -> np.ndarray:
    """Convert multi-channel audio to mono by averaging channels."""
    if audio.ndim == 1:
        return audio
    with set_event("branch_selected"):
        logger.info("branch=mono_convert channels=%s", audio.shape[1])
    return np.mean(audio, axis=1)


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio from orig_sr to target_sr using linear interpolation."""
    if orig_sr == target_sr:
        return audio
    with set_event("branch_selected"):
        logger.info("branch=resample orig_sr=%s target_sr=%s", orig_sr, target_sr)
    duration = len(audio) / orig_sr
    target_len = int(round(duration * target_sr))
    indices = np.linspace(0, len(audio) - 1, target_len)
    return np.interp(indices, np.arange(len(audio)), audio)
