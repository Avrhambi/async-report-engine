"""Background report generation.

Self-contained: computes only from rows already in PostgreSQL, makes zero
network calls outside docker-compose, and a retry produces byte-identical
output because the aggregation is deterministic.
"""
from __future__ import annotations

import datetime

import structlog
from celery import Task

from app.core.database import SyncSessionLocal
from app.repositories.sync_report_repo import SyncReportRepository
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


def _compute(task_id: str) -> None:
    with SyncSessionLocal() as session:
        repo = SyncReportRepository(session)
        report = repo.get_by_task_id(task_id)
        if report is None:
            logger.warning("report_row_missing", task_id=task_id)
            return

        repo.set_status(task_id, "STARTED")

        params = dict(report.params or {})
        date_from = datetime.date.fromisoformat(params["date_from"])
        date_to = datetime.date.fromisoformat(params["date_to"])
        group_by = list(params.get("group_by", []))

        result = repo.report_aggregates(date_from, date_to, group_by)
        repo.save_result(task_id, report.report_type, params, result)
        logger.info("report_generated", task_id=task_id)


def _dead_letter(task_id: str) -> None:
    """Route a permanently failed job to DEAD_LETTER without crashing."""
    with SyncSessionLocal() as session:
        SyncReportRepository(session).set_status(task_id, "DEAD_LETTER")


def run_generate_report(task: Task, task_id: str) -> None:
    """Task body, separated from the decorator so it is directly testable."""
    try:
        _compute(task_id)
    except Exception as exc:  # noqa: BLE001
        retries = task.request.retries if task.request else 0
        if retries >= (task.max_retries or 0):
            logger.error("report_dead_letter", task_id=task_id, error=str(exc))
            _dead_letter(task_id)
            return
        raise task.retry(exc=exc) from exc


@celery_app.task(
    bind=True,
    name="app.workers.tasks.generate_report_task",
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=False,
)
def generate_report_task(self: Task, task_id: str) -> None:
    run_generate_report(self, task_id)
