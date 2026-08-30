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


def test_permanent_failure_routes_to_dead_letter(repo: MagicMock):
    dead_repo = MagicMock()
    call = {"n": 0}

    def _repo_factory(_session):
        call["n"] += 1
        return repo if call["n"] == 1 else dead_repo

    fake_self = SimpleNamespace(
        request=SimpleNamespace(retries=3), max_retries=3
    )
    repo.get_by_task_id.side_effect = RuntimeError("db down")

    with patch.object(tasks, "SyncSessionLocal", return_value=_fake_session_cm(repo)), \
         patch.object(tasks, "SyncReportRepository", side_effect=_repo_factory):
        # Terminal retry: body swallows the error and routes to DLQ.
        tasks.run_generate_report(fake_self, "rpt_1")

    dead_repo.set_status.assert_called_once_with("rpt_1", "DEAD_LETTER")


def test_transient_failure_retries(repo: MagicMock):
    retried = {"called": False}

    def _retry(exc=None):
        retried["called"] = True
        return RuntimeError("retry scheduled")

    fake_self = SimpleNamespace(
        request=SimpleNamespace(retries=0), max_retries=3, retry=_retry
    )
    repo.get_by_task_id.side_effect = RuntimeError("transient")

    with patch.object(tasks, "SyncSessionLocal", return_value=_fake_session_cm(repo)), \
         patch.object(tasks, "SyncReportRepository", return_value=repo), \
         pytest.raises(RuntimeError):
        tasks.run_generate_report(fake_self, "rpt_1")

    assert retried["called"] is True
