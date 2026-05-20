import os
import tempfile
from datetime import datetime

import numpy as np
import soundfile as sf
from nisqa.NISQA_model import nisqaModel

from audioqas.logging import get_logger, set_event
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

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "weights", "nisqa.tar")
NISQA_TARGET_SR = 48000
logger = get_logger(__name__)

NISQA_LABELS = {
    "OVRL": "整体听感",
    "NOI":  "噪音度",
    "DIS":  "连续性",
    "COL":  "染色度",
    "LOUD": "响度",
}

NISQA_DESCRIPTIONS = {
    "OVRL": {
        "Bad": "刺耳难听", "Poor": "勉强能听", "Fair": "还行",
        "Good": "清晰舒服", "Excellent": "非常清亮",
    },
    "NOI": {
        "Bad": "噪音轰鸣", "Poor": "噪音明显", "Fair": "有些杂音",
        "Good": "安静清爽", "Excellent": "寂静纯净",
    },
    "DIS": {
        "Bad": "断断续续", "Poor": "偶尔卡顿", "Fair": "基本流畅",
        "Good": "流畅稳定", "Excellent": "完美连贯",
    },
    "COL": {
        "Bad": "严重失真", "Poor": "明显变味", "Fair": "轻微变色",
        "Good": "还原自然", "Excellent": "透明纯净",
    },
    "LOUD": {
        "Bad": "忽大忽小", "Poor": "偏轻或偏响", "Fair": "基本正常",
        "Good": "适中舒服", "Excellent": "完美响度",
    },
}

NISQA_METAPHORS = {
    "OVRL": {
        "Bad": "\"电话里杂音比话音大，完全没法说\"",
        "Poor": "\"像在很吵的路上打电话，勉强能听\"",
        "Fair": "\"像在办公室通话，有小杂音但不影响理解\"",
        "Good": "\"像用干净的手机录音，听起来很舒服\"",
        "Excellent": "\"像在录音棚里录的音质，完美\"",
    },
    "NOI": {
        "Bad": "\"像在工地旁说话，杂音淹没了人声\"",
        "Poor": "\"像在路边打电话，风吹车过影响听清\"",
        "Fair": "\"背景像在咖啡馆，有轻微杂音\"",
        "Good": "\"像在干净的小会议室，背景很安静\"",
        "Excellent": "\"背景完全无声，像在绝对安静的房间\"",
    },
    "DIS": {
        "Bad": "\"像断线电话，话说到一半就断了\"",
        "Poor": "\"像信号不好的视频通话，偶尔卡一下\"",
        "Fair": "\"基本流畅，偶尔轻微延迟\"",
        "Good": "\"像稳定的视频通话，没有中断\"",
        "Excellent": "\"像面对面说话，完全连贯无中断\"",
    },
    "COL": {
        "Bad": "\"像用劣质喇叭放的声音，严重失真\"",
        "Poor": "\"像电话线传输的声音，有点变味\"",
        "Fair": "\"声音基本自然，但有轻微改变\"",
        "Good": "\"像正常手机录音，音色还原好\"",
        "Excellent": "\"像录音棚原声录制，完全透明\"",
    },
    "LOUD": {
        "Bad": "\"忽大忽小，像信号不稳的广播\"",
        "Poor": "\"偏轻或偏响，像音量没调好\"",
        "Fair": "\"音量基本正常，略有起伏\"",
        "Good": "\"像正常调节好的通话，音量适中\"",
        "Excellent": "\"音量完美，像专业录音的响度平衡\"",
    },
}

DimensionRegistry.register("NISQA", NISQA_LABELS, NISQA_DESCRIPTIONS, NISQA_METAPHORS)

def _preprocess_for_nisqa(audio_path: str) -> tuple[str, dict]:
    ext = os.path.splitext(audio_path)[1].lower()
    is_video = ext in VIDEO_EXTS
    pipeline_steps = ["source_video" if is_video else "source_audio"]
    if is_video:
        if not PREPROCESS_SETTINGS["extract_audio"]:
            raise ValueError("video_extract_disabled")
        out_name = build_preprocessed_name(audio_path, target_sr=NISQA_TARGET_SR, is_video=True)
        audio_path = _extract_audio(audio_path, NISQA_TARGET_SR, out_name)
        pipeline_steps.append("extract_audio")

    audio, orig_sr = sf.read(audio_path)
    orig_channels = 1 if audio.ndim == 1 else audio.shape[1]
    duration = len(audio) / orig_sr
    need_resample = orig_sr != NISQA_TARGET_SR
    need_mono = audio.ndim > 1
    with set_event("preprocess_decision"):
        logger.debug(
            "preprocess_decision file=%s is_video=%s orig_sr=%s target_sr=%s need_mono=%s need_resample=%s",
            audio_path,
            is_video,
            orig_sr,
            NISQA_TARGET_SR,
            need_mono,
            need_resample,
        )

    if not need_resample and not need_mono:
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
    if need_resample and not PREPROCESS_SETTINGS["resample"]:
        raise ValueError("resample_disabled")

    if need_mono:
        pipeline_steps.append("to_mono")
        audio = _to_mono(audio)

    if need_resample:
        pipeline_steps.append("keep_48k")
        audio = _resample(audio, orig_sr, NISQA_TARGET_SR)
    else:
        pipeline_steps.append("keep_48k")

    out_name = build_preprocessed_name(audio_path, target_sr=NISQA_TARGET_SR, is_video=is_video)
    out_path = os.path.join(_ensure_preprocess_dir(), out_name)
    sf.write(out_path, audio, NISQA_TARGET_SR)
    with set_event("preprocess_succeeded"):
        logger.info(
            "preprocess_succeeded file=%s output=%s sr=%s pipeline=%s",
            audio_path,
            out_path,
            NISQA_TARGET_SR,
            format_pipeline_steps(pipeline_steps, "NISQA"),
        )

    return out_path, {
        "original_sr": orig_sr,
        "original_channels": orig_channels,
        "duration": duration,
        "preprocessed": True,
        "preprocessed_path": out_path,
        "pipeline_steps": pipeline_steps,
    }


class NISQAScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "NISQA"

    @property
    def version(self) -> str:
        return "v2"

    @property
    def dimensions(self) -> list[str]:
        return ["OVRL", "NOI", "DIS", "COL", "LOUD"]

    def score(self, audio_path: str) -> ScoreResult:
        processed_path, meta = _preprocess_for_nisqa(audio_path)

        args = {
            "mode": "predict_file",
            "pretrained_model": WEIGHTS_PATH,
            "deg": processed_path,
            "output_dir": tempfile.mkdtemp(),
            "tr_parallel": False,
            "tr_bs_val": 1,
            "tr_num_workers": 0,
            "ms_channel": 0,
        }

        nisqa = nisqaModel(args)
        df = nisqa.predict()

        row = df.iloc[0]
        dim_scores = {
            "OVRL": float(row["mos_pred"]),
            "NOI":  float(row["noi_pred"]),
            "DIS":  float(row["dis_pred"]),
            "COL":  float(row["col_pred"]),
            "LOUD": float(row["loud_pred"]),
        }

        descs = DimensionRegistry.descriptions("NISQA")
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
