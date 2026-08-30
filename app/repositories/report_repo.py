"""All async SQLAlchemy queries against the reports table (API side).

The worker's writes live in sync_report_repo.py; the aggregation SQL lives
there once, not duplicated here.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Report


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_pending(
        self, task_id: str, report_type: str, params: dict[str, Any]
    ) -> Report:
        report = Report(
            id=str(uuid.uuid4()),
            task_id=task_id,
            report_type=report_type,
            params=params,
            status="PENDING",
            result=None,
        )
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def get_by_task_id(self, task_id: str) -> Report | None:
        stmt = select(Report).where(Report.task_id == task_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()
