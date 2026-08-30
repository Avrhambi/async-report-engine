"""Orchestration for background report generation and retrieval."""
from __future__ import annotations

import uuid
from typing import Any

from app.domain.exceptions import ReportNotFoundError
from app.repositories.report_repo import ReportRepository


def _new_task_id() -> str:
    return f"rpt_{uuid.uuid4().hex[:12]}"


class ReportService:
    def __init__(self, report_repo: ReportRepository) -> None:
        self.report_repo = report_repo

    async def dispatch(
        self, report_type: str, params: dict[str, Any]
    ) -> dict[str, str]:
        task_id = _new_task_id()
        # The row must exist before .delay() so the first poll never 404s.
        await self.report_repo.create_pending(task_id, report_type, params)

        # Imported here to keep the worker module out of the API import path
        # when Celery's broker is unavailable during unit tests.
        from app.workers.tasks import generate_report_task

        generate_report_task.delay(task_id)
        return {"task_id": task_id, "status": "PENDING"}

    async def get(self, task_id: str) -> dict[str, Any]:
        report = await self.report_repo.get_by_task_id(task_id)
        if report is None:
            raise ReportNotFoundError(task_id)
        return {
            "task_id": report.task_id,
            "status": report.status,
            "result": report.result,
        }
