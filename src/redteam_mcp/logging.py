"""Structured logging for Red-Team MCP.

Every tool call produces a JSON audit record (who, what, when, args, result
size, status) so an engagement can be replayed for post-op forensics.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

import structlog


_configured = False


def configure_logging(
    level: str = "INFO",
    log_dir: str | Path | None = None,
    json_mode: bool = True,
) -> None:
    """Configure ``structlog`` + stdlib ``logging`` for the process.

    Safe to call multiple times; only the first call takes effect.
    """

    global _configured
    if _configured:
        return
    _configured = True

    numeric = getattr(logging, level.upper(), logging.INFO)

    # ----- stdlib root logger -----
    root = logging.getLogger()
    root.setLevel(numeric)
    root.handlers.clear()

    # Log to stderr so stdout stays reserved for MCP JSON-RPC frames.
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setLevel(numeric)
    root.addHandler(stderr_handler)

    if log_dir:
        log_path = Path(log_dir).expanduser().resolve()
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path / "server.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric)
        root.addHandler(file_handler)

    # ----- structlog processors -----
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    if json_mode:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        processors=processors,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger with ``logger_name`` context set."""

    return structlog.get_logger(name).bind(logger_name=name)


def audit_event(logger: structlog.stdlib.BoundLogger, event: str, **fields: Any) -> None:
    """Write an audit-level record.

    Audit records are tagged ``audit=True`` for easy post-run grep.
    """

    logger.info(event, audit=True, **fields)
