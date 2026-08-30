from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AnalyticsMetricsResponse,
    EventBatchRequest,
    EventBatchResponse,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportResponse,
)
from app.core.database import get_db
from app.core.redis import get_redis
from app.domain.exceptions import ReportNotFoundError
from app.repositories.order_repo import OrderRepository
from app.repositories.report_repo import ReportRepository
from app.services.analytics_service import AnalyticsService
from app.services.ingestion_service import IngestionService
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/v1")


def get_ingestion_service(
    db: AsyncSession = Depends(get_db), redis_client: Redis = Depends(get_redis)
) -> IngestionService:
    return IngestionService(OrderRepository(db), redis_client)


def get_report_service(db: AsyncSession = Depends(get_db)) -> ReportService:
    return ReportService(ReportRepository(db))


def get_analytics_service(
    db: AsyncSession = Depends(get_db), redis_client: Redis = Depends(get_redis)
) -> AnalyticsService:
    return AnalyticsService(OrderRepository(db), redis_client)


@router.post(
    "/events/batch",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EventBatchResponse,
)
async def ingest_events_batch(
    payload: EventBatchRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    service: IngestionService = Depends(get_ingestion_service),
) -> EventBatchResponse:
    events = [e.model_dump() for e in payload.events]
    result = await service.ingest_batch(idempotency_key, events)
    return EventBatchResponse(**result)


@router.post(
    "/reports/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ReportGenerateResponse,
)
async def generate_report(
    payload: ReportGenerateRequest,
    service: ReportService = Depends(get_report_service),
) -> ReportGenerateResponse:
    params = {
        "date_from": payload.date_from.isoformat(),
        "date_to": payload.date_to.isoformat(),
        "group_by": payload.group_by,
    }
    result = await service.dispatch(payload.report_type, params)
    return ReportGenerateResponse(**result)


@router.get("/reports/{task_id}", response_model=ReportResponse)
async def get_report(
    task_id: str, service: ReportService = Depends(get_report_service)
) -> ReportResponse:
    try:
        result = await service.get(task_id)
    except ReportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No report found for task_id {task_id!r}",
        ) from None
    return ReportResponse(**result)


@router.get("/analytics/metrics", response_model=AnalyticsMetricsResponse)
async def get_analytics_metrics(
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsMetricsResponse:
    return AnalyticsMetricsResponse(**await service.get_metrics())
