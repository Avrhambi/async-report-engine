"""Worker tests: state transitions, deterministic re-run, DLQ routing.

The DB is mocked; aggregation SQL correctness is covered in
test_integration.py against a real Postgres.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from app.workers import tasks


def _fake_session_cm(repo: MagicMock) -> MagicMock:
    cm = MagicMock()
    cm.__enter__.return_value = MagicMock()
    cm.__exit__.return_value = False
    return cm


@pytest.fixture
def repo() -> MagicMock:
    r = MagicMock()
    r.get_by_task_id.return_value = SimpleNamespace(
        task_id="rpt_1",
        report_type="revenue_summary",
        params={
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
            "group_by": ["region"],
        },
    )
    r.report_aggregates.return_value = {"total_revenue": 100.0, "order_count": 3}
    return r


def test_compute_transitions_and_saves(repo: MagicMock):
    with patch.object(tasks, "SyncSessionLocal", return_value=_fake_session_cm(repo)), \
         patch.object(tasks, "SyncReportRepository", return_value=repo):
        tasks._compute("rpt_1")

    repo.set_status.assert_called_once_with("rpt_1", "STARTED")
    repo.save_result.assert_called_once()
    saved = repo.save_result.call_args.args
    assert saved[0] == "rpt_1"
    assert saved[3] == {"total_revenue": 100.0, "order_count": 3}


def test_rerun_is_deterministic(repo: MagicMock):
    with patch.object(tasks, "SyncSessionLocal", return_value=_fake_session_cm(repo)), \
         patch.object(tasks, "SyncReportRepository", return_value=repo):
        tasks._compute("rpt_1")
        first = repo.save_result.call_args.args[3]
        tasks._compute("rpt_1")
        second = repo.save_result.call_args.args[3]
    assert first == second


def test_on_failure_routes_to_dead_letter(repo: MagicMock):
    """When retries are exhausted Celery calls on_failure; the report row is
    moved to DEAD_LETTER and the worker keeps running."""
    dead_repo = MagicMock()

    with patch.object(tasks, "SyncSessionLocal", return_value=_fake_session_cm(repo)), \
         patch.object(tasks, "SyncReportRepository", return_value=dead_repo):
        task = tasks.ReportTask()
        task.on_failure(
            RuntimeError("permanent"), "celery-uuid", ("rpt_1",), {}, None
        )

    dead_repo.set_status.assert_called_once_with("rpt_1", "DEAD_LETTER")


def test_task_declares_autoretry_with_backoff():
    opts = tasks.generate_report_task
    assert opts.max_retries == 3
    assert Exception in opts.autoretry_for
    assert opts.retry_backoff is True
