import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AnalyticsMetrics, EventCreate
from app.core.database import get_db
from app.repositories.event_repo import EventRepository
from app.repositories.report_repo import ReportRepository
from app.services.analytics_service import AnalyticsService
from app.workers.tasks import generate_report_task

router = APIRouter()

@router.post("/events/batch", status_code=202)
async def ingest_events(events: list[EventCreate], db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    repo = EventRepository(db)
    count = await repo.create_batch(events)
    return {"message": f"Successfully queued {count} events"}

@router.post("/reports/generate", status_code=202)
async def generate_report(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    task_id = str(uuid.uuid4())
    repo = ReportRepository(db)
    
    # Create a pending DB record first
    await repo.create_report(task_id)
    
    # Dispatch the heavy task to RabbitMQ / Celery worker
    generate_report_task.delay(task_id)
    
    return {"task_id": task_id, "status": "202 Accepted"}

@router.get("/reports/{task_id}")
async def get_report(task_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    repo = ReportRepository(db)
    report = await repo.get_report(task_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    return {
        "task_id": report.id,
        "status": report.status,
        "result_summary": report.result_summary,
        "created_at": report.created_at,
        "updated_at": report.updated_at
    }

@router.get("/analytics/metrics", response_model=AnalyticsMetrics)
async def get_analytics_metrics(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    service = AnalyticsService(db)
    metrics = await service.get_metrics()
    return metrics
