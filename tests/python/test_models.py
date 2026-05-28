from audioqas.models import BaseScorer, ScoreResult, score_to_grade
from audioqas.models.base import GRADE_MAP


class TestScoreToGrade:
    def test_excellent(self):
        assert score_to_grade(4.8) == "Excellent"
        assert score_to_grade(4.5) == "Excellent"

    def test_good(self):
        assert score_to_grade(4.0) == "Good"
        assert score_to_grade(4.49) == "Good"

    def test_fair(self):
        assert score_to_grade(3.0) == "Fair"
        assert score_to_grade(3.99) == "Fair"

    def test_poor(self):
        assert score_to_grade(2.0) == "Poor"
        assert score_to_grade(2.99) == "Poor"

    def test_bad(self):
        assert score_to_grade(0.0) == "Bad"
        assert score_to_grade(1.99) == "Bad"


class TestModelExports:
    def test_base_exports_available(self):
        assert BaseScorer is not None
        assert ScoreResult is not None

    def test_grade_map_descending_thresholds(self):
        thresholds = [threshold for threshold, _ in GRADE_MAP]
        assert thresholds == sorted(thresholds, reverse=True)

    def test_grade_labels_complete(self):
        labels = [label for _, label in GRADE_MAP]
        assert labels == ["Excellent", "Good", "Fair", "Poor", "Bad"]


def test_shared_preprocessing_functions_exist():
    """Shared preprocessor module should export all required functions."""
    from audioqas.core.preprocessor import VIDEO_EXTS, _ensure_preprocess_dir, _to_mono, _resample, _extract_audio
    assert ".mp4" in VIDEO_EXTS
    assert ".mov" in VIDEO_EXTS
    assert ".wmv" in VIDEO_EXTS


def test_to_mono_converts_stereo():
    """_to_mono should average channels to produce mono."""
    import numpy as np
    from audioqas.core.preprocessor import _to_mono
    stereo = np.array([[1.0, 2.0], [3.0, 4.0]])  # 2 samples, 2 channels
    mono = _to_mono(stereo)
    assert mono.shape == (2,)
    assert mono[0] == 1.5
    assert mono[1] == 3.5


def test_resample_changes_length():
    """_resample should change the array length according to the target rate."""
    import numpy as np
    from audioqas.core.preprocessor import _resample
    audio = np.ones(48000)  # 1 second at 48kHz
    resampled = _resample(audio, 48000, 16000)
    assert len(resampled) == 16000


def _wav_with_zero_sizes_and_pcm_payload(sample_rate: int = 16000) -> bytes:
    import numpy as np

    pcm = np.array([0, 16384, -16384, 8192], dtype="<i2").tobytes()
    return (
        b"RIFF"
        + (36).to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + sample_rate.to_bytes(4, "little")
        + (sample_rate * 2).to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
        + b"data"
        + (0).to_bytes(4, "little")
        + pcm
    )


def test_read_audio_recovers_wav_with_zero_data_size_and_pcm_payload(tmp_path):
    import numpy as np
    from audioqas.core.preprocessor import read_audio

    audio_path = tmp_path / "damaged_header.wav"
    audio_path.write_bytes(_wav_with_zero_sizes_and_pcm_payload())

    audio, sr = read_audio(str(audio_path))

    assert sr == 16000
    assert np.allclose(audio, np.array([0.0, 0.5, -0.5, 0.25]), atol=1e-6)


def test_default_preprocess_dir_is_project_tmp_dir():
    from pathlib import Path
    from audioqas.core import preprocessor

    expected = Path(preprocessor.__file__).resolve().parents[2] / ".tmp" / "preprocessed"
    actual = Path(preprocessor.DEFAULT_PREPROCESS_DIR)

    assert actual == expected


def test_analysis_output_keys_are_five_computed_metrics():
    """AudioAnalyzer metric descriptions should only include the 5 computed metrics, not SNR/Stereo."""
    from audioqas.models.analysis import METRIC_DESCRIPTIONS
    assert set(METRIC_DESCRIPTIONS.keys()) == {"LUFS", "LRA", "TruePeak", "Clipping", "THD"}
    assert "SNR" not in METRIC_DESCRIPTIONS
    assert "Stereo" not in METRIC_DESCRIPTIONS


def test_analysis_lufs_handles_short_audio_without_crashing():
    import numpy as np
    from audioqas.models.analysis import _compute_lufs

    lufs, lra = _compute_lufs(np.zeros(4800), 48000)

    assert lufs == -70.0
    assert lra == 0.0


def test_video_preprocess_marks_dnsmos_as_preprocessed(monkeypatch):
    import numpy as np
    from audioqas.models import dnsmos

    extracted = "/tmp/video_from_video_16000Hz_mono.wav"
    monkeypatch.setattr(dnsmos, "_extract_audio", lambda path, target_sr, out_name=None: extracted)
    monkeypatch.setattr(dnsmos.sf, "read", lambda path: (np.zeros(16000), 16000))

    processed_path, meta = dnsmos._preprocess_audio("sample.mp4")

    assert processed_path == extracted
    assert meta["preprocessed"] is True
    assert meta["preprocessed_path"] == extracted


def test_video_preprocess_marks_nisqa_as_preprocessed(monkeypatch):
    import numpy as np
    from audioqas.models import nisqa

    extracted = "/tmp/video_from_video_48000Hz_mono.wav"
    monkeypatch.setattr(nisqa, "_extract_audio", lambda path, target_sr, out_name=None: extracted)
    monkeypatch.setattr(nisqa.sf, "read", lambda path: (np.zeros(48000), 48000))

    processed_path, meta = nisqa._preprocess_for_nisqa("sample.mov")

    assert processed_path == extracted
    assert meta["preprocessed"] is True
    assert meta["preprocessed_path"] == extracted


def test_video_preprocess_marks_aes_as_preprocessed(monkeypatch):
    import numpy as np
    from audioqas.models import audiobox_aesthetics

    extracted = "/tmp/video_from_video_mono.wav"
    monkeypatch.setattr(audiobox_aesthetics, "_extract_audio", lambda path, target_sr, out_name=None: extracted)
    monkeypatch.setattr(audiobox_aesthetics.sf, "read", lambda path: (np.zeros(48000), 48000))

    processed_path, meta = audiobox_aesthetics._preprocess_for_aes("sample.mkv")

    assert processed_path == extracted
    assert meta["preprocessed"] is True
    assert meta["preprocessed_path"] == extracted


def test_video_preprocess_marks_analysis_as_preprocessed(monkeypatch):
    import numpy as np
    from audioqas.models import analysis

    extracted = "/tmp/video_from_video_mono.wav"
    mono_audio = np.zeros(48000)
    monkeypatch.setattr(analysis, "_extract_audio", lambda path, target_sr, out_name=None: extracted)
    monkeypatch.setattr(analysis.sf, "read", lambda path: (mono_audio, 48000))

    processed_path, audio, sr, meta = analysis._preprocess_for_analysis("sample.avi")

    assert processed_path == extracted
    assert audio is mono_audio
    assert sr == 48000
    assert meta["preprocessed"] is True
    assert meta["preprocessed_path"] == extracted


def test_dnsmos_preprocess_logs_passthrough_branch(tmp_path, monkeypatch):
    import numpy as np
    from audioqas.logging import setup_logging
    from audioqas.models import dnsmos

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    monkeypatch.setattr(dnsmos.sf, "read", lambda path: (np.zeros(16000), 16000))

    dnsmos._preprocess_audio("sample.wav")

    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "branch=passthrough" in text


def test_dnsmos_preprocess_debug_logs_capture_input_decision(tmp_path, monkeypatch):
    import numpy as np
    from audioqas.logging import setup_logging
    from audioqas.models import dnsmos

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    monkeypatch.setattr(dnsmos.sf, "read", lambda path: (np.zeros((16000, 2)), 16000))
    monkeypatch.setattr(dnsmos.sf, "write", lambda *args, **kwargs: None)
    monkeypatch.setattr(dnsmos, "_ensure_preprocess_dir", lambda: str(tmp_path))

    dnsmos._preprocess_audio("sample.wav")

    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "preprocess_decision" in text
    assert "need_mono=True" in text


def test_dnsmos_passthrough_pipeline_steps_are_explicit(tmp_path, monkeypatch):
    import numpy as np
    from audioqas.models import dnsmos

    monkeypatch.setattr(dnsmos.sf, "read", lambda path: (np.zeros(16000), 16000))

    _, meta = dnsmos._preprocess_audio("sample.wav")

    assert meta["pipeline_steps"] == ["source_audio", "passthrough"]


def test_nisqa_preprocess_debug_logs_capture_input_decision(tmp_path, monkeypatch):
    import numpy as np
    from audioqas.logging import setup_logging
    from audioqas.models import nisqa

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    monkeypatch.setattr(nisqa.sf, "read", lambda path: (np.zeros((48000, 2)), 48000))
    monkeypatch.setattr(nisqa.sf, "write", lambda *args, **kwargs: None)
    monkeypatch.setattr(nisqa, "_ensure_preprocess_dir", lambda: str(tmp_path))

    nisqa._preprocess_for_nisqa("sample.wav")

    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "preprocess_decision" in text
    assert "target_sr=48000" in text


def test_analysis_preprocess_debug_logs_capture_input_decision(tmp_path, monkeypatch):
    import numpy as np
    from audioqas.logging import setup_logging
    from audioqas.models import analysis

    setup_logging(log_dir=tmp_path / "log", level="DEBUG", max_mb=1, backup_count=2)
    monkeypatch.setattr(analysis.sf, "read", lambda path: (np.zeros((48000, 2)), 48000))
    monkeypatch.setattr(analysis.sf, "write", lambda *args, **kwargs: None)
    monkeypatch.setattr(analysis, "_ensure_preprocess_dir", lambda: str(tmp_path))

    analysis._preprocess_for_analysis("sample.wav")

    text = (tmp_path / "log" / "audioqas.log").read_text(encoding="utf-8")
    assert "preprocess_decision" in text
    assert "need_mono=True" in text
