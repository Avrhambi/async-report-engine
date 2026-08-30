"""app.core.logging: JSON output and idempotent configuration."""
from __future__ import annotations

import json

from app.core import logging as app_logging


def test_configure_logging_is_idempotent() -> None:
    app_logging._configured = False
    app_logging.configure_logging()
    first = app_logging._configured
    app_logging.configure_logging()
    assert first is True
    assert app_logging._configured is True


def test_get_logger_emits_json(capsys) -> None:
    app_logging._configured = False
    logger = app_logging.get_logger("test")
    logger.info("something_happened", task_id="rpt_1", count=3)

    out = capsys.readouterr().out.strip().splitlines()[-1]
    record = json.loads(out)
    assert record["event"] == "something_happened"
    assert record["task_id"] == "rpt_1"
    assert record["count"] == 3
    assert record["level"] == "info"
    assert "timestamp" in record
