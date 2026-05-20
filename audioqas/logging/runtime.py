from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path


_request_id_var: ContextVar[str] = ContextVar("audioqas_request_id", default="-")
_scene_var: ContextVar[str] = ContextVar("audioqas_scene", default="-")
_event_var: ContextVar[str] = ContextVar("audioqas_event", default="-")
_configured = False


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        record.scene = _scene_var.get()
        record.event = _event_var.get()
        record.level_short = record.levelname[:1]
        return True


def _formatter() -> logging.Formatter:
    return logging.Formatter(
        "[%(asctime)s.%(msecs)03d][%(thread)d][%(level_short)s][%(request_id)s][%(scene)s][%(event)s]:(%(filename)s:%(lineno)d): [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _rotating_handler(path: Path, *, level: int, max_bytes: int, backup_count: int) -> RotatingFileHandler:
    handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(_formatter())
    handler.addFilter(_ContextFilter())
    return handler


def setup_logging(
    *,
    log_dir: str | Path | None = None,
    level: str | None = None,
    max_mb: int | None = None,
    backup_count: int | None = None,
) -> None:
    global _configured

    resolved_dir = Path(log_dir or os.environ.get("AUDIOQAS_LOG_DIR") or Path(__file__).resolve().parents[2] / "log")
    resolved_dir.mkdir(parents=True, exist_ok=True)
    resolved_level_name = (level or os.environ.get("AUDIOQAS_LOG_LEVEL", "DEBUG")).upper()
    resolved_level = getattr(logging, resolved_level_name, logging.DEBUG)
    resolved_max_bytes = int((max_mb or int(os.environ.get("AUDIOQAS_LOG_MAX_MB", "20"))) * 1024 * 1024)
    resolved_backup_count = backup_count or int(os.environ.get("AUDIOQAS_LOG_BACKUP_COUNT", "20"))

    root = logging.getLogger("audioqas")
    root.setLevel(resolved_level)
    root.handlers.clear()
    root.propagate = False

    app_handler = _rotating_handler(
        resolved_dir / "audioqas.log",
        level=resolved_level,
        max_bytes=resolved_max_bytes,
        backup_count=resolved_backup_count,
    )
    error_handler = _rotating_handler(
        resolved_dir / "audioqas.error.log",
        level=logging.ERROR,
        max_bytes=resolved_max_bytes,
        backup_count=resolved_backup_count,
    )

    root.addHandler(app_handler)
    root.addHandler(error_handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    if not _configured:
        setup_logging()
    return logging.getLogger(f"audioqas.{name}" if not name.startswith("audioqas.") else name)


def get_request_id() -> str:
    return _request_id_var.get()


@contextmanager
def log_context(*, request_id: str | None = None, scene: str | None = None, event: str | None = None):
    tokens: list[tuple[ContextVar[str], object]] = []
    if request_id is not None:
        tokens.append((_request_id_var, _request_id_var.set(request_id)))
    if scene is not None:
        tokens.append((_scene_var, _scene_var.set(scene)))
    if event is not None:
        tokens.append((_event_var, _event_var.set(event)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


@contextmanager
def set_event(event: str):
    token = _event_var.set(event)
    try:
        yield
    finally:
        _event_var.reset(token)
