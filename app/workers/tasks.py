import asyncio

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.domain.models import Event
from app.repositories.report_repo import ReportRepository
from app.workers.celery_app import celery_app


async def process_report_async(task_id: str) -> None:
    async with AsyncSessionLocal() as session:
        repo = ReportRepository(session)
        # Update status to indicate processing has begun
        await repo.update_report(task_id, status="STARTED", summary=None)
        
        try:
            # Simulate a heavy aggregation query
            stmt = select(Event.event_type, func.count(Event.id)).group_by(Event.event_type)
            result = await session.execute(stmt)
            summary = {row[0]: row[1] for row in result.all()}
            
            # Save success state
            await repo.update_report(task_id, status="SUCCESS", summary=summary)
        except Exception as e:
            # Save failure state
            await repo.update_report(task_id, status="FAILURE", summary={"error": str(e)})
            raise

from typing import Any


@celery_app.task(bind=True, max_retries=3, autoretry_for=(Exception,))  # type: ignore
def generate_report_task(self: Any, task_id: str) -> Any:
    # Celery workers are synchronous by default, so we run our async code inside an event loop
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(process_report_async(task_id))
