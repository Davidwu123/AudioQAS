import os
import subprocess
import tempfile
from datetime import datetime

import numpy as np
import soundfile as sf
from nisqa.NISQA_model import nisqaModel

from audioqas.models.base import BaseScorer, ScoreResult, score_to_grade
from audioqas.core.dimensions import DimensionRegistry

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "weights", "nisqa.tar")
PREPROCESS_DIR = os.path.expanduser("~/Library/Application Support/AudioQAS/preprocessed")
NISQA_TARGET_SR = 48000

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
    out_name = _preprocessed_name(video_path, NISQA_TARGET_SR, is_video=True)
    out_path = os.path.join(_ensure_preprocess_dir(), out_name)
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
           "-ar", str(NISQA_TARGET_SR), "-ac", "1", "-y", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def _preprocess_for_nisqa(audio_path: str) -> tuple[str, dict]:
    ext = os.path.splitext(audio_path)[1].lower()
    is_video = ext in VIDEO_EXTS
    if is_video:
        audio_path = _extract_audio(audio_path)

    audio, orig_sr = sf.read(audio_path)
    orig_channels = 1 if audio.ndim == 1 else audio.shape[1]
    duration = len(audio) / orig_sr

    need_resample = orig_sr != NISQA_TARGET_SR
    need_mono = audio.ndim > 1

    if not need_resample and not need_mono:
        return audio_path, {
            "original_sr": orig_sr,
            "original_channels": orig_channels,
            "duration": duration,
            "preprocessed": False,
            "preprocessed_path": "",
        }

    if need_mono:
        audio = np.mean(audio, axis=1)

    if need_resample:
        duration = len(audio) / orig_sr
        target_len = int(round(duration * NISQA_TARGET_SR))
        indices = np.linspace(0, len(audio) - 1, target_len)
        audio = np.interp(indices, np.arange(len(audio)), audio)

    out_name = _preprocessed_name(audio_path, NISQA_TARGET_SR, is_video=is_video)
    out_path = os.path.join(_ensure_preprocess_dir(), out_name)
    sf.write(out_path, audio, NISQA_TARGET_SR)

    return out_path, {
        "original_sr": orig_sr,
        "original_channels": orig_channels,
        "duration": duration,
        "preprocessed": True,
        "preprocessed_path": out_path,
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
        )
