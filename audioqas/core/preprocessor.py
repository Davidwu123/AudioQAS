"""Shared audio preprocessing utilities for all model scorers."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf

from audioqas.logging import get_logger, set_event


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREPROCESS_DIR = str(PROJECT_ROOT / ".tmp" / "preprocessed")
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"}
FFMPEG_AUDIO_EXTS = {".mp3", ".aac", ".m4a"}
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


def ensure_non_empty_audio(audio: np.ndarray) -> None:
    if audio.size == 0 or len(audio) == 0:
        raise ValueError("empty_audio")


def _find_wav_chunks(raw: bytes) -> tuple[dict[str, bytes], int | None, int | None]:
    if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        return {}, None, None

    chunks: dict[str, bytes] = {}
    data_offset = None
    data_size = None
    offset = 12
    while offset + 8 <= len(raw):
        chunk_id = raw[offset:offset + 4]
        chunk_size = int.from_bytes(raw[offset + 4:offset + 8], "little")
        chunk_start = offset + 8
        chunk_end = min(chunk_start + chunk_size, len(raw))
        chunk_key = chunk_id.decode("ascii", errors="ignore")
        chunks[chunk_key] = raw[chunk_start:chunk_end]
        if chunk_id == b"data":
            data_offset = chunk_start
            data_size = chunk_size
            break
        offset = chunk_start + chunk_size + (chunk_size % 2)
    return chunks, data_offset, data_size


def _decode_pcm_payload(payload: bytes, channels: int, bits_per_sample: int) -> np.ndarray:
    if bits_per_sample == 8:
        audio = (np.frombuffer(payload, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif bits_per_sample == 16:
        audio = np.frombuffer(payload, dtype="<i2").astype(np.float64) / 32768.0
    elif bits_per_sample == 24:
        values = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 3)
        signed = (
            values[:, 0].astype(np.int32)
            | (values[:, 1].astype(np.int32) << 8)
            | (values[:, 2].astype(np.int32) << 16)
        )
        signed = np.where(signed & 0x800000, signed | ~0xFFFFFF, signed)
        audio = signed.astype(np.float64) / 8388608.0
    elif bits_per_sample == 32:
        audio = np.frombuffer(payload, dtype="<i4").astype(np.float64) / 2147483648.0
    else:
        return np.array([], dtype=np.float64)

    if channels > 1:
        audio = audio.reshape(-1, channels)
    return audio.astype(np.float32, copy=False)


def _read_wav_with_damaged_size_header(audio_path: str) -> tuple[np.ndarray, int]:
    raw = Path(audio_path).read_bytes()
    chunks, data_offset, declared_data_size = _find_wav_chunks(raw)
    fmt = chunks.get("fmt ")
    if fmt is None or len(fmt) < 16 or data_offset is None or declared_data_size is None:
        return np.array([], dtype=np.float32), 0

    audio_format = int.from_bytes(fmt[0:2], "little")
    channels = int.from_bytes(fmt[2:4], "little")
    sample_rate = int.from_bytes(fmt[4:8], "little")
    block_align = int.from_bytes(fmt[12:14], "little")
    bits_per_sample = int.from_bytes(fmt[14:16], "little")
    if audio_format != 1 or channels <= 0 or sample_rate <= 0 or block_align <= 0:
        return np.array([], dtype=np.float32), sample_rate

    available_size = max(0, len(raw) - data_offset)
    payload_size = declared_data_size if declared_data_size > 0 else available_size
    payload_size = min(payload_size, available_size)
    payload_size -= payload_size % block_align
    if payload_size <= 0:
        return np.array([], dtype=np.float32), sample_rate
    payload = raw[data_offset:data_offset + payload_size]
    return _decode_pcm_payload(payload, channels, bits_per_sample), sample_rate


def read_audio(audio_path: str) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(audio_path)
    if audio.size > 0 or Path(audio_path).suffix.lower() != ".wav":
        return audio, sample_rate

    recovered_audio, recovered_sr = _read_wav_with_damaged_size_header(audio_path)
    if recovered_audio.size == 0:
        return audio, sample_rate
    with set_event("preprocess_recovered"):
        logger.info("wav_header_recovered file=%s sr=%s samples=%s", audio_path, recovered_sr, len(recovered_audio))
    return recovered_audio, recovered_sr


def format_pipeline_steps(steps: list[str], model_label: str) -> str:
    mapping = {
        "source_video": "原始视频",
        "source_audio": "原始文件",
        "extract_audio": "抽取音轨",
        "decode_audio": "解码音频",
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
    if shutil.which("ffmpeg") is None:
        raise ValueError("ffmpeg_missing")
    out_path = os.path.join(_ensure_preprocess_dir(), out_name)
    with set_event("branch_selected"):
        logger.info("branch=video_extract file=%s target_sr=%s output=%s", video_path, target_sr, out_path)
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
           "-ar", str(target_sr), "-ac", "1", "-y", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def _decode_audio_with_ffmpeg(audio_path: str, target_sr: int, out_name: str | None = None) -> str:
    """Decode compressed audio to mono WAV for model preprocessing."""
    if out_name is None:
        out_name = build_preprocessed_name(audio_path, target_sr=target_sr)
    if shutil.which("ffmpeg") is None:
        raise ValueError("ffmpeg_missing")
    out_path = os.path.join(_ensure_preprocess_dir(), out_name)
    with set_event("branch_selected"):
        logger.info("branch=audio_decode file=%s target_sr=%s output=%s", audio_path, target_sr, out_path)
    cmd = [
        "ffmpeg",
        "-i",
        audio_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(target_sr),
        "-ac",
        "1",
        "-y",
        out_path,
    ]
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
