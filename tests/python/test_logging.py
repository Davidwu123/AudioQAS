from pathlib import Path


def test_setup_logging_creates_log_dir_and_files(tmp_path):
    from audioqas.logging import runtime as logging_runtime

    log_dir = tmp_path / "log"

    logging_runtime.setup_logging(log_dir=log_dir, level="DEBUG", max_mb=1, backup_count=2)
    logger = logging_runtime.get_logger("tests.logging")
    logger.info("hello logging")

    assert log_dir.exists()
    assert (log_dir / "audioqas.log").exists()
    assert (log_dir / "audioqas.error.log").exists()


def test_log_context_propagates_request_id_and_scene(tmp_path):
    from audioqas.logging import runtime as logging_runtime

    log_dir = tmp_path / "log"

    logging_runtime.setup_logging(log_dir=log_dir, level="DEBUG", max_mb=1, backup_count=2)
    with logging_runtime.log_context(request_id="req_test_001", scene="single"):
        logging_runtime.get_logger("tests.logging").info("context visible")

    text = (log_dir / "audioqas.log").read_text(encoding="utf-8")
    assert "[req_test_001]" in text
    assert "[single]" in text


def test_error_log_receives_error_entries(tmp_path):
    from audioqas.logging import runtime as logging_runtime

    log_dir = tmp_path / "log"

    logging_runtime.setup_logging(log_dir=log_dir, level="DEBUG", max_mb=1, backup_count=2)
    logging_runtime.get_logger("tests.logging").error("boom")

    app_text = (log_dir / "audioqas.log").read_text(encoding="utf-8")
    error_text = (log_dir / "audioqas.error.log").read_text(encoding="utf-8")
    assert "boom" in app_text
    assert "boom" in error_text


def test_log_rotation_creates_incremented_suffix_file(tmp_path):
    from audioqas.logging import runtime as logging_runtime

    log_dir = tmp_path / "log"

    logging_runtime.setup_logging(log_dir=log_dir, level="DEBUG", max_mb=1, backup_count=2)
    logger = logging_runtime.get_logger("tests.logging")
    payload = "x" * (1024 * 256)
    for _ in range(8):
        logger.info(payload)

    assert (log_dir / "audioqas.log").exists()
    assert (log_dir / "audioqas.log.1").exists()
