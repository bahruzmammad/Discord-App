"""
Logging setup — supports Rich console output, plain text, and JSON.
Import `get_logger` and call it once per module.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO", fmt: str = "rich", log_file: Optional[str] = None) -> None:
    """
    Configure root logger. Call once at application startup.

    Args:
        level:    Standard logging level string (DEBUG, INFO, WARNING, ERROR).
        fmt:      Output format — "rich" for coloured console, "json" for
                  structured JSON lines, "plain" for classic text.
        log_file: Optional path to a file handler (appended alongside console).
    """
    level_int = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level_int)
    root.handlers.clear()

    if fmt == "rich":
        try:
            from rich.logging import RichHandler
            handler: logging.Handler = RichHandler(
                rich_tracebacks=True,
                show_path=False,
                markup=True,
            )
            handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
        except ImportError:
            handler = _plain_handler()
    elif fmt == "json":
        handler = _json_handler()
    else:
        handler = _plain_handler()

    handler.setLevel(level_int)
    root.addHandler(handler)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level_int)
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%SZ",
            )
        )
        root.addHandler(fh)

    # Silence noisy third-party loggers
    for noisy in ("discord", "aiohttp", "urllib3", "chardet", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _plain_handler() -> logging.Handler:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    )
    return h


def _json_handler() -> logging.Handler:
    """Simple JSON line formatter without extra dependencies."""
    import json as _json
    import time

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            return _json.dumps(
                {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
                    "level": record.levelname,
                    "logger": record.name,
                    "msg": record.getMessage(),
                },
                ensure_ascii=False,
            )

    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    return h


def get_logger(name: str) -> logging.Logger:
    """Return a named child logger. Always call this instead of logging.getLogger directly."""
    return logging.getLogger(name)
