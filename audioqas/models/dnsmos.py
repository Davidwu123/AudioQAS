import os
import subprocess
from datetime import datetime

import numpy as np
import soundfile as sf
import speechmos.dnsmos

from audioqas.models.base import BaseScorer, ScoreResult, score_to_grade
from audioqas.core.dimensions import DimensionRegistry

TARGET_SR = 16000
PREPROCESS_DIR = os.path.expanduser("~/Library/Application Support/AudioQAS/preprocessed")

DNSMOS_LABELS = {
    "OVRL": "整体听感",
    "SIG": "语音清晰度",
    "BAK": "背景干净度",
}

DNSMOS_DESCRIPTIONS = {
    "OVRL": {
        "Bad": "刺耳难听",
        "Poor": "勉强能听",
        "Fair": "还行",
        "Good": "清晰舒服",
        "Excellent": "非常清亮",
    },
    "SIG": {
        "Bad": "模糊难辨",
        "Poor": "含糊不清",
        "Fair": "基本清楚",
        "Good": "清晰自然",
        "Excellent": "纯净透亮",
    },
    "BAK": {
        "Bad": "噪音轰鸣",
        "Poor": "噪音明显",
        "Fair": "有些杂音",
        "Good": "安静清爽",
        "Excellent": "寂静纯净",
    },
}

DNSMOS_METAPHORS = {
    "OVRL": {
        "Bad": "\"电话里杂音比话音大，完全没法说\"",
        "Poor": "\"像在很吵的路上打电话，勉强能听\"",
        "Fair": "\"像在办公室通话，有小杂音但不影响理解\"",
        "Good": "\"像用干净的手机录音，听起来很舒服\"",
        "Excellent": "\"像在录音棚里录的音质，完美\"",
    },
    "SIG": {
        "Bad": "\"说话像在水下，只能听到模糊声\"",
        "Poor": "\"含糊不清，听得懂但很费力\"",
        "Fair": "\"像电话信号不太好，说话还清晰但少了细节\"",
        "Good": "\"像正常面对面说话，声音还原好\"",
        "Excellent": "\"像录音棚近距离录制的效果，每个音都通透\"",
    },
    "BAK": {
        "Bad": "\"像在工地旁说话，杂音淹没了人声\"",
        "Poor": "\"像在路边打电话，风吹车过影响听清\"",
        "Fair": "\"背景像在咖啡馆，有轻微杂音\"",
        "Good": "\"像在干净的小会议室，背景很安静\"",
        "Excellent": "\"背景完全无声，像在绝对安静的房间\"",
    },
}

DimensionRegistry.register("DNSMOS", DNSMOS_LABELS, DNSMOS_DESCRIPTIONS, DNSMOS_METAPHORS)

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"}


def _preprocessed_name(original_path: str, target_sr: int, is_video: bool = False) -> str:
    base = os.path.splitext(os.path.basename(original_path))[0]
    parts = [base]
    if is_video:
        parts.append("from_video")
    parts.append(f"{target_sr}Hz")
    parts.append("mono")
    return "_".join(parts) + ".wav"


def _ensure_preprocess_dir() -> str:
    os.makedirs(PREPROCESS_DIR, exist_ok=True)
    return PREPROCESS_DIR


def _extract_audio(video_path: str) -> str:
    out_name = _preprocessed_name(video_path, TARGET_SR, is_video=True)
    out_path = os.path.join(_ensure_preprocess_dir(), out_name)
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
           "-ar", str(TARGET_SR), "-ac", "1", "-y", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr:
        return audio
    duration = len(audio) / orig_sr
    target_len = int(round(duration * target_sr))
    indices = np.linspace(0, len(audio) - 1, target_len)
    return np.interp(indices, np.arange(len(audio)), audio)


def _to_mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio
    return np.mean(audio, axis=1)


def _preprocess_audio(audio_path: str) -> tuple[str, dict]:
    ext = os.path.splitext(audio_path)[1].lower()
    is_video = ext in VIDEO_EXTS
    if is_video:
        audio_path = _extract_audio(audio_path)

    audio, orig_sr = sf.read(audio_path)
    orig_channels = 1 if audio.ndim == 1 else audio.shape[1]
    duration = len(audio) / orig_sr
    need_resample = orig_sr != TARGET_SR
    need_mono = audio.ndim > 1

    if not need_resample and not need_mono:
        return audio_path, {
            "original_sr": orig_sr,
            "original_channels": orig_channels,
            "duration": duration,
            "preprocessed": False,
            "preprocessed_path": "",
        }

    audio = _to_mono(audio)
    audio = _resample(audio, orig_sr, TARGET_SR)

    out_name = _preprocessed_name(audio_path, TARGET_SR, is_video=is_video)
    out_path = os.path.join(_ensure_preprocess_dir(), out_name)
    sf.write(out_path, audio, TARGET_SR)

    return out_path, {
        "original_sr": orig_sr,
        "original_channels": orig_channels,
        "duration": duration,
        "preprocessed": True,
        "preprocessed_path": out_path,
    }


class DNSMOSScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "DNSMOS"

    @property
    def version(self) -> str:
        return "v8"

    @property
    def dimensions(self) -> list[str]:
        return ["OVRL", "SIG", "BAK"]

    def score(self, audio_path: str) -> ScoreResult:
        processed_path, meta = _preprocess_audio(audio_path)

        result = speechmos.dnsmos.run(processed_path, TARGET_SR)

        dim_scores: dict[str, float] = {
            "OVRL": float(result["ovrl_mos"]),
            "SIG": float(result["sig_mos"]),
            "BAK": float(result["bak_mos"]),
        }

        descs = DimensionRegistry.descriptions("DNSMOS")
        dimensions: dict = {}
        descriptions: dict[str, str] = {}
        for dim_name, raw_score in dim_scores.items():
            grade = score_to_grade(raw_score)
            dimensions[dim_name] = {
                "score": raw_score,
                "grade": grade,
                "description": descs[dim_name][grade],
            }
            descriptions[dim_name] = descs[dim_name][grade]

        overall_grade = score_to_grade(dim_scores["OVRL"])

        return ScoreResult(
            eval_type="mos",
            model_name=self.name,
            model_version=self.version,
            dimensions=dimensions,
            grade=overall_grade,
            descriptions=descriptions,
            timestamp=datetime.now().isoformat(),
            file_path=audio_path,
            original_sr=meta["original_sr"],
            original_channels=meta["original_channels"],
            duration=meta["duration"],
            preprocessed=meta["preprocessed"],
            preprocessed_path=meta["preprocessed_path"],
        )
