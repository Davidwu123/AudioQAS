import os
from datetime import datetime

import numpy as np
import soundfile as sf

from audioqas.logging import get_logger, set_event
from audioqas.models.base import BaseScorer, ScoreResult
from audioqas.core.dimensions import DimensionRegistry
from audioqas.core.preprocessor import (
    PREPROCESS_SETTINGS,
    VIDEO_EXTS,
    _ensure_preprocess_dir,
    _extract_audio,
    _to_mono,
    build_preprocessed_name,
    current_preprocess_settings,
    format_pipeline_steps,
)

AES_GRADE_MAP = [
    (8.0, "Excellent"),
    (6.0, "Good"),
    (4.0, "Fair"),
    (2.0, "Poor"),
    (0.0, "Bad"),
]


def aes_score_to_grade(score: float) -> str:
    for threshold, grade in AES_GRADE_MAP:
        if score >= threshold:
            return grade
    return "Bad"


AES_LABELS = {
    "PQ": "制作质量",
    "CE": "内容享受",
    "CU": "内容有用",
    "PC": "制作复杂度",
}

AES_DESCRIPTIONS = {
    "PQ": {
        "Excellent": "制作精良", "Good": "制作良好", "Fair": "制作一般",
        "Poor": "制作粗糙", "Bad": "制作极差",
    },
    "CE": {
        "Excellent": "极度享受", "Good": "比较享受", "Fair": "还行",
        "Poor": "不太享受", "Bad": "毫无享受",
    },
    "CU": {
        "Excellent": "非常有用", "Good": "比较有用", "Fair": "有些用处",
        "Poor": "用处不大", "Bad": "毫无用处",
    },
    "PC": {
        "Excellent": "制作复杂精致", "Good": "制作较复杂", "Fair": "制作简单",
        "Poor": "制作非常简单", "Bad": "制作极简粗糙",
    },
}

AES_METAPHORS = {
    "PQ": {
        "Excellent": "\"像专业录音棚出品，音质无可挑剔\"",
        "Good": "\"制作质量不错，听感舒适\"",
        "Fair": "\"制作质量还行，没有明显问题\"",
        "Poor": "\"制作粗糙，有明显的质量问题\"",
        "Bad": "\"制作极差，听起来非常不舒服\"",
    },
    "CE": {
        "Excellent": "\"非常享受，愿意反复聆听\"",
        "Good": "\"比较享受，听得很舒服\"",
        "Fair": "\"还行，没有特别想再听\"",
        "Poor": "\"不太享受，听感一般\"",
        "Bad": "\"毫无享受感，不想再听\"",
    },
    "CU": {
        "Excellent": "\"内容极具价值，信息量丰富\"",
        "Good": "\"内容比较有用\"",
        "Fair": "\"内容有些用处\"",
        "Poor": "\"内容用处不大\"",
        "Bad": "\"内容毫无价值\"",
    },
    "PC": {
        "Excellent": "\"制作手法多样，层次丰富\"",
        "Good": "\"制作有一定复杂度\"",
        "Fair": "\"制作比较简单\"",
        "Poor": "\"制作非常简单\"",
        "Bad": "\"制作极简，几乎无处理\"",
    },
}

DimensionRegistry.register("AudioBox-Aesthetics", AES_LABELS, AES_DESCRIPTIONS, AES_METAPHORS)

AES_TARGET_SR = 48000
logger = get_logger(__name__)


def _preprocess_for_aes(audio_path: str) -> tuple[str, dict]:
    ext = os.path.splitext(audio_path)[1].lower()
    is_video = ext in VIDEO_EXTS
    pipeline_steps = ["source_video" if is_video else "source_audio"]
    if is_video:
        if not PREPROCESS_SETTINGS["extract_audio"]:
            raise ValueError("video_extract_disabled")
        out_name = build_preprocessed_name(audio_path, is_video=True)
        audio_path = _extract_audio(audio_path, AES_TARGET_SR, out_name)
        pipeline_steps.append("extract_audio")

    audio, orig_sr = sf.read(audio_path)
    orig_channels = 1 if audio.ndim == 1 else audio.shape[1]
    duration = len(audio) / orig_sr

    need_mono = audio.ndim > 1

    if not need_mono:
        with set_event("branch_selected"):
            logger.info("branch=passthrough file=%s sr=%s channels=%s", audio_path, orig_sr, orig_channels)
        pipeline_steps.append("keep_48k")
        return audio_path, {
            "original_sr": orig_sr,
            "original_channels": orig_channels,
            "duration": duration,
            "preprocessed": is_video,
            "preprocessed_path": audio_path if is_video else "",
            "pipeline_steps": pipeline_steps,
        }

    if need_mono and not PREPROCESS_SETTINGS["to_mono"]:
        raise ValueError("mono_convert_disabled")

    pipeline_steps.extend(["to_mono", "keep_48k"])
    audio = _to_mono(audio)
    out_name = build_preprocessed_name(audio_path, is_video=is_video)
    out_path = os.path.join(_ensure_preprocess_dir(), out_name)
    sf.write(out_path, audio, orig_sr)
    with set_event("preprocess_succeeded"):
        logger.info(
            "preprocess_succeeded file=%s output=%s sr=%s pipeline=%s",
            audio_path,
            out_path,
            orig_sr,
            format_pipeline_steps(pipeline_steps, "AudioBox Aesthetics"),
        )

    return out_path, {
        "original_sr": orig_sr,
        "original_channels": orig_channels,
        "duration": duration,
        "preprocessed": True,
        "preprocessed_path": out_path,
        "pipeline_steps": pipeline_steps,
    }


class AudioBoxAestheticsScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "AudioBox-Aesthetics"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def dimensions(self) -> list[str]:
        return ["PQ", "CE", "CU", "PC"]

    def score(self, audio_path: str) -> ScoreResult:
        processed_path, meta = _preprocess_for_aes(audio_path)

        from audiobox_aesthetics.infer import initialize_predictor
        import torch
        predictor = initialize_predictor()
        # Force CPU on macOS (MPS doesn't support autocast)
        predictor.model = predictor.model.to("cpu")
        predictor.device = "cpu"
        result = predictor.forward([{"path": processed_path}])

        aes_scores = result[0]
        dim_scores: dict[str, float] = {
            "PQ": float(aes_scores["PQ"]),
            "CE": float(aes_scores["CE"]),
            "CU": float(aes_scores["CU"]),
            "PC": float(aes_scores["PC"]),
        }

        descs = DimensionRegistry.descriptions("AudioBox-Aesthetics")
        dimensions: dict = {}
        descriptions: dict[str, str] = {}
        for dim_name, raw_score in dim_scores.items():
            grade = aes_score_to_grade(raw_score)
            dimensions[dim_name] = {
                "score": raw_score,
                "grade": grade,
                "description": descs[dim_name][grade],
            }
            descriptions[dim_name] = descs[dim_name][grade]

        overall_grade = aes_score_to_grade(dim_scores["PQ"])

        return ScoreResult(
            eval_type="analysis",
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
            pipeline_steps=meta["pipeline_steps"],
            preprocess_settings=current_preprocess_settings(),
        )
