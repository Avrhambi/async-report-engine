from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

OrderStatus = Literal[
    "pending", "paid", "shipped", "delivered", "cancelled", "refunded"
]


class OrderEvent(BaseModel):
    order_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    status: OrderStatus
    total_amount: float = Field(ge=0)
    region: str = Field(min_length=1)
    created_at: datetime.datetime


class EventBatchRequest(BaseModel):
    events: list[OrderEvent] = Field(min_length=1, max_length=1000)


class EventBatchResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    ingested: int
    duplicates: int


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class ReportGenerateRequest(BaseModel):
    report_type: Literal["revenue_summary"] = "revenue_summary"
    date_from: datetime.date
    date_to: datetime.date
    group_by: list[Literal["region", "status"]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _range_is_ordered(self) -> ReportGenerateRequest:
        if self.date_to < self.date_from:
            raise ValueError("date_to must not be earlier than date_from")
        return self


class ReportGenerateResponse(BaseModel):
    task_id: str
    status: str


class ReportResponse(BaseModel):
    task_id: str
    status: str
    result: dict | None = None


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class AnalyticsMetricsResponse(BaseModel):
    window: str
    revenue: float
    order_count: int
    average_order_value: float
    orders_by_region: dict[str, int]
