import os
import subprocess
from datetime import datetime
from typing import TypedDict

import numpy as np
import soundfile as sf
import pyloudnorm
from scipy.signal import find_peaks
from scipy.fft import rfft, rfftfreq


PREPROCESS_DIR = os.path.expanduser("~/Library/Application Support/AudioQAS/preprocessed")
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"}


class MetricScore(TypedDict):
    value: float
    unit: str
    grade: str          # "Good" / "Warning" / "Poor"
    description: str
    threshold_good: float
    threshold_warn: float


class AnalysisResult(TypedDict):
    eval_type: str      # "analysis"
    model_name: str     # "AudioAnalyzer"
    model_version: str  # "v1"
    metrics: dict[str, MetricScore]
    grade: str          # overall grade
    timestamp: str
    file_path: str
    original_sr: int
    original_channels: int
    duration: float
    preprocessed: bool
    preprocessed_path: str


# 3-level thresholds
LUFS_GOOD = (-23, -16)     # -23 to -16 LUFS
LUFS_WARN = (-26, -14)     # -26 to -14 LUFS (outside Good)
LRA_GOOD_MAX = 15
LRA_WARN_MAX = 20
PEAK_GOOD_MAX = -1.0       # dBTP
PEAK_WARN_MAX = 0.0        # dBTP
CLIP_GOOD_MAX = 0
CLIP_WARN_MAX = 10
THD_GOOD_MAX = 1.0         # percent
THD_WARN_MAX = 5.0         # percent


def _metric_grade(value: float, good_range: tuple | None = None,
                  good_max: float | None = None,
                  warn_max: float | None = None) -> str:
    if good_range:
        low, high = good_range
        if low <= value <= high:
            return "Good"
        if warn_range := (low - abs(low) * 0.15, high + abs(high) * 0.15):
            wl, wh = warn_range
            if wl <= value <= wh:
                return "Warning"
        return "Poor"
    if good_max is not None:
        if value <= good_max:
            return "Good"
        if warn_max is not None and value <= warn_max:
            return "Warning"
    return "Poor"


def _preprocessed_name(original_path: str, is_video: bool = False) -> str:
    base = os.path.splitext(os.path.basename(original_path))[0]
    parts = [base]
    if is_video:
        parts.append("from_video")
    parts.append("mono")
    return "_".join(parts) + ".wav"


def _ensure_preprocess_dir() -> str:
    os.makedirs(PREPROCESS_DIR, exist_ok=True)
    return PREPROCESS_DIR


def _extract_audio(video_path: str) -> str:
    out_name = _preprocessed_name(video_path, is_video=True)
    out_path = os.path.join(_ensure_preprocess_dir(), out_name)
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ac", "1", "-y", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def _preprocess_for_analysis(audio_path: str) -> tuple[str, dict]:
    ext = os.path.splitext(audio_path)[1].lower()
    is_video = ext in VIDEO_EXTS
    if is_video:
        audio_path = _extract_audio(audio_path)

    audio, orig_sr = sf.read(audio_path)
    orig_channels = 1 if audio.ndim == 1 else audio.shape[1]
    duration = len(audio) / orig_sr

    need_mono = audio.ndim > 1

    if not need_mono:
        return audio_path, audio, orig_sr, {
            "original_sr": orig_sr,
            "original_channels": orig_channels,
            "duration": duration,
            "preprocessed": False,
            "preprocessed_path": "",
        }

    audio = np.mean(audio, axis=1)
    out_name = _preprocessed_name(audio_path, is_video=is_video)
    out_path = os.path.join(_ensure_preprocess_dir(), out_name)
    sf.write(out_path, audio, orig_sr)

    return out_path, audio, orig_sr, {
        "original_sr": orig_sr,
        "original_channels": orig_channels,
        "duration": duration,
        "preprocessed": True,
        "preprocessed_path": out_path,
    }


def _compute_lufs(audio: np.ndarray, sr: int) -> tuple[float, float]:
    meter = pyloudnorm.Meter(sr)
    lufs = meter.integrated_loudness(audio)
    lra = meter.loudness_range(audio)
    if lufs == -np.inf:
        lufs = -70.0
    return float(lufs), float(lra)


def _compute_true_peak(audio: np.ndarray, sr: int) -> float:
    peak = np.max(np.abs(audio))
    peak_dbtp = 20 * np.log10(peak) if peak > 0 else -np.inf
    return float(peak_dbtp)


def _detect_clipping(audio: np.ndarray) -> int:
    threshold = 1.0
    clipped = np.where(np.abs(audio) >= threshold)[0]
    if len(clipped) == 0:
        return 0
    # Count distinct clipping events (groups of consecutive samples)
    groups = np.split(clipped, np.where(np.diff(clipped) > 1)[0] + 1)
    return len(groups)


def _compute_thd(audio: np.ndarray, sr: int) -> float:
    if len(audio) < sr:
        return 0.0
    # Use first 1 second for THD estimation
    segment = audio[:sr]
    n = len(segment)
    yf = np.abs(rfft(segment))
    xf = rfftfreq(n, 1.0 / sr)

    # Find fundamental frequency (strongest peak above 50Hz)
    min_freq_idx = np.searchsorted(xf, 50)
    peaks, _ = find_peaks(yf[min_freq_idx:], height=np.max(yf) * 0.01)
    if len(peaks) == 0:
        return 0.0

    peak_idx = peaks[np.argmax(yf[min_freq_idx:][peaks])] + min_freq_idx
    fundamental_power = yf[peak_idx] ** 2

    # Sum harmonic powers (2nd through 5th)
    fundamental_freq = xf[peak_idx]
    harmonic_power = 0.0
    for h in range(2, 6):
        h_freq = fundamental_freq * h
        if h_freq >= sr / 2:
            break
        h_idx = np.searchsorted(xf, h_freq)
        if h_idx < len(yf):
            # Search within ±5 bins for harmonic peak
            window = max(0, h_idx - 5), min(len(yf), h_idx + 6)
            h_peak = np.max(yf[window[0]:window[1]])
            harmonic_power += h_peak ** 2

    if fundamental_power == 0:
        return 0.0
    thd_percent = np.sqrt(harmonic_power / fundamental_power) * 100
    return float(min(thd_percent, 100.0))


METRIC_LABELS = {
    "LUFS": "响度 (LUFS)",
    "LRA": "动态范围 (LRA)",
    "TruePeak": "真实峰值 (dBTP)",
    "Clipping": "削波事件",
    "THD": "总谐波失真 (%)",
}

METRIC_DESCRIPTIONS = {
    "LUFS": {"Good": "响度适中", "Warning": "响度偏轻或偏响", "Poor": "响度异常"},
    "LRA": {"Good": "动态范围合理", "Warning": "动态偏大或偏小", "Poor": "动态范围异常"},
    "TruePeak": {"Good": "峰值安全", "Warning": "峰值接近上限", "Poor": "峰值超限"},
    "Clipping": {"Good": "无削波", "Warning": "轻微削波", "Poor": "严重削波"},
    "THD": {"Good": "失真极低", "Warning": "有可感知失真", "Poor": "严重失真"},
}


class AudioAnalyzer:
    """Independent class, not inheriting BaseScorer."""

    def analyze(self, audio_path: str) -> AnalysisResult:
        processed_path, audio, sr, meta = _preprocess_for_analysis(audio_path)

        lufs, lra = _compute_lufs(audio, sr)
        true_peak = _compute_true_peak(audio, sr)
        clipping = _detect_clipping(audio)
        thd = _compute_thd(audio, sr)

        metrics: dict[str, MetricScore] = {}

        # LUFS
        lufs_grade = _metric_grade(lufs, good_range=LUFS_GOOD)
        metrics["LUFS"] = MetricScore(
            value=lufs, unit="LUFS", grade=lufs_grade,
            description=METRIC_DESCRIPTIONS["LUFS"][lufs_grade],
            threshold_good=LUFS_GOOD[0], threshold_warn=LUFS_WARN[0],
        )

        # LRA
        lra_grade = _metric_grade(lra, good_max=LRA_GOOD_MAX, warn_max=LRA_WARN_MAX)
        metrics["LRA"] = MetricScore(
            value=lra, unit="LU", grade=lra_grade,
            description=METRIC_DESCRIPTIONS["LRA"][lra_grade],
            threshold_good=LRA_GOOD_MAX, threshold_warn=LRA_WARN_MAX,
        )

        # True Peak
        tp_grade = _metric_grade(true_peak, good_max=PEAK_GOOD_MAX, warn_max=PEAK_WARN_MAX)
        metrics["TruePeak"] = MetricScore(
            value=true_peak, unit="dBTP", grade=tp_grade,
            description=METRIC_DESCRIPTIONS["TruePeak"][tp_grade],
            threshold_good=PEAK_GOOD_MAX, threshold_warn=PEAK_WARN_MAX,
        )

        # Clipping
        clip_grade = _metric_grade(clipping, good_max=CLIP_GOOD_MAX, warn_max=CLIP_WARN_MAX)
        metrics["Clipping"] = MetricScore(
            value=clipping, unit="次", grade=clip_grade,
            description=METRIC_DESCRIPTIONS["Clipping"][clip_grade],
            threshold_good=CLIP_GOOD_MAX, threshold_warn=CLIP_WARN_MAX,
        )

        # THD
        thd_grade = _metric_grade(thd, good_max=THD_GOOD_MAX, warn_max=THD_WARN_MAX)
        metrics["THD"] = MetricScore(
            value=thd, unit="%", grade=thd_grade,
            description=METRIC_DESCRIPTIONS["THD"][thd_grade],
            threshold_good=THD_GOOD_MAX, threshold_warn=THD_WARN_MAX,
        )

        # Overall grade: worst of all metrics
        grade_order = {"Good": 0, "Warning": 1, "Poor": 2}
        worst = max(metrics.values(), key=lambda m: grade_order[m["grade"]])
        overall_grade = worst["grade"]

        return AnalysisResult(
            eval_type="analysis",
            model_name="AudioAnalyzer",
            model_version="v1",
            metrics=metrics,
            grade=overall_grade,
            timestamp=datetime.now().isoformat(),
            file_path=audio_path,
            original_sr=meta["original_sr"],
            original_channels=meta["original_channels"],
            duration=meta["duration"],
            preprocessed=meta["preprocessed"],
            preprocessed_path=meta["preprocessed_path"],
        )
