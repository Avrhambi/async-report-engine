"""Domain models. This layer imports nothing from other app/ layers."""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_id: Mapped[str] = mapped_column(String, unique=True)
    customer_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    region: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    __table_args__ = (
        # Matches the report/analytics predicate (created_at range) and covers
        # total_amount so the aggregates come from an Index Only Scan.
        Index(
            "idx_orders_created_at",
            text("created_at DESC"),
            postgresql_include=["total_amount"],
        ),
        # Kept to match INTENT.md's named contract and back the GROUP BY paths.
        Index("idx_orders_status_created_at", "status", text("created_at DESC")),
        Index("idx_orders_region_created_at", "region", text("created_at DESC")),
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, unique=True)
    report_type: Mapped[str] = mapped_column(String)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
