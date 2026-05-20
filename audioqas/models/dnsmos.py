import os
from datetime import datetime

import numpy as np
import soundfile as sf
import speechmos.dnsmos

from audioqas.models.base import BaseScorer, ScoreResult, score_to_grade
from audioqas.core.dimensions import DimensionRegistry
from audioqas.core.preprocessor import (
    PREPROCESS_SETTINGS,
    VIDEO_EXTS,
    _ensure_preprocess_dir,
    _extract_audio,
    _to_mono,
    _resample,
    build_preprocessed_name,
    current_preprocess_settings,
    format_pipeline_steps,
)
from audioqas.logging import get_logger, set_event

TARGET_SR = 16000
logger = get_logger(__name__)

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

def _preprocess_audio(audio_path: str) -> tuple[str, dict]:
    ext = os.path.splitext(audio_path)[1].lower()
    is_video = ext in VIDEO_EXTS
    pipeline_steps = ["source_video" if is_video else "source_audio"]
    if is_video:
        if not PREPROCESS_SETTINGS["extract_audio"]:
            raise ValueError("video_extract_disabled")
        out_name = build_preprocessed_name(audio_path, target_sr=TARGET_SR, is_video=True)
        audio_path = _extract_audio(audio_path, TARGET_SR, out_name)
        pipeline_steps.append("extract_audio")

    audio, orig_sr = sf.read(audio_path)
    orig_channels = 1 if audio.ndim == 1 else audio.shape[1]
    duration = len(audio) / orig_sr
    need_resample = orig_sr != TARGET_SR
    need_mono = audio.ndim > 1
    with set_event("preprocess_decision"):
        logger.debug(
            "preprocess_decision file=%s is_video=%s orig_sr=%s target_sr=%s need_mono=%s need_resample=%s",
            audio_path,
            is_video,
            orig_sr,
            TARGET_SR,
            need_mono,
            need_resample,
        )

    if not need_resample and not need_mono:
        with set_event("branch_selected"):
            logger.info("branch=passthrough file=%s sr=%s channels=%s", audio_path, orig_sr, orig_channels)
        pipeline_steps.append("passthrough")
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
    if need_resample and not PREPROCESS_SETTINGS["resample"]:
        raise ValueError("resample_disabled")

    if need_mono:
        pipeline_steps.append("to_mono")
    audio = _to_mono(audio)
    if need_resample:
        pipeline_steps.append("resample_16k")
    audio = _resample(audio, orig_sr, TARGET_SR)

    out_name = build_preprocessed_name(audio_path, target_sr=TARGET_SR, is_video=is_video)
    out_path = os.path.join(_ensure_preprocess_dir(), out_name)
    sf.write(out_path, audio, TARGET_SR)
    with set_event("preprocess_succeeded"):
        logger.info(
            "preprocess_succeeded file=%s output=%s sr=%s pipeline=%s",
            audio_path,
            out_path,
            TARGET_SR,
            format_pipeline_steps(pipeline_steps, "DNSMOS"),
        )

    return out_path, {
        "original_sr": orig_sr,
        "original_channels": orig_channels,
        "duration": duration,
        "preprocessed": True,
        "preprocessed_path": out_path,
        "pipeline_steps": pipeline_steps,
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
            pipeline_steps=meta["pipeline_steps"],
            preprocess_settings=current_preprocess_settings(),
        )
