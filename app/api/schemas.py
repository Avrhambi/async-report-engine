from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EventCreate(BaseModel):
    user_id: str
    event_type: str
    payload: dict[str, Any]

class ReportResponse(BaseModel):
    task_id: str
    status: str
    result_summary: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime | None = None

class AnalyticsMetrics(BaseModel):
    total_events: int
    events_by_type: dict[str, int]
