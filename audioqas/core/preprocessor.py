import os
import subprocess
import tempfile

import numpy as np
import soundfile as sf

TARGET_SR = 16000

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"}


def _extract_audio_from_video(video_path: str) -> str:
    tmp_dir = tempfile.mkdtemp(prefix="mos_video_extract_")
    tmp_audio = os.path.join(tmp_dir, "extracted.wav")
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", str(TARGET_SR),
        "-ac", "1",
        "-y", tmp_audio,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return tmp_audio


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


class AudioPreprocessor:
    def preprocess(self, audio_path: str) -> tuple[str, dict]:
        ext = os.path.splitext(audio_path)[1].lower()

        if ext in VIDEO_EXTENSIONS:
            audio_path = _extract_audio_from_video(audio_path)

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
            }

        audio = _to_mono(audio)
        audio = _resample(audio, orig_sr, TARGET_SR)

        tmp_dir = tempfile.mkdtemp(prefix="mos_preprocess_")
        tmp_path = os.path.join(tmp_dir, "preprocessed.wav")
        sf.write(tmp_path, audio, TARGET_SR)

        return tmp_path, {
            "original_sr": orig_sr,
            "original_channels": orig_channels,
            "duration": duration,
            "preprocessed": True,
        }