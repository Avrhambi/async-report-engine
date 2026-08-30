"""All SQLAlchemy queries against the reports table live here."""
from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
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

    async def set_status(self, task_id: str, status: str) -> None:
        report = await self.get_by_task_id(task_id)
        if report is not None:
            report.status = status
            report.updated_at = datetime.datetime.now(datetime.timezone.utc)
            await self.session.commit()

    async def save_result(
        self,
        task_id: str,
        report_type: str,
        params: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """Idempotent upsert of the finished report by task_id.

        Re-running a deterministic job overwrites with an identical result.
        """
        stmt = (
            pg_insert(Report)
            .values(
                id=str(uuid.uuid4()),
                task_id=task_id,
                report_type=report_type,
                params=params,
                status="SUCCESS",
                result=result,
            )
            .on_conflict_do_update(
                index_elements=["task_id"],
                set_={
                    "status": "SUCCESS",
                    "result": result,
                    "updated_at": datetime.datetime.now(datetime.timezone.utc),
                },
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()
