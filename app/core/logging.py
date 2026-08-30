"""Centralised structured-logging setup.

Call ``configure_logging()`` once at process start (API and worker), then
obtain loggers with ``get_logger(__name__)``. Output is line-delimited JSON so
container log collectors can parse it directly.
"""
from __future__ import annotations

import logging

import structlog

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotently configure stdlib logging + structlog for JSON output."""
    global _configured
    if _configured:
        return

    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger, configuring logging on first use."""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)
