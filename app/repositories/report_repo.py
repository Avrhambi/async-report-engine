from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Report


class ReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_report(self, task_id: str) -> Report:
        report = Report(id=task_id, status="PENDING")
        self.session.add(report)
        await self.session.commit()
        return report

    async def get_report(self, task_id: str) -> Report | None:
        result = await self.session.execute(select(Report).where(Report.id == task_id))
        return result.scalars().first()

    async def update_report(self, task_id: str, status: str, summary: dict[str, Any] | None) -> Report | None:
        report = await self.get_report(task_id)
        if report:
            report.status = status  # type: ignore
            report.result_summary = summary  # type: ignore
            await self.session.commit()
        return report
