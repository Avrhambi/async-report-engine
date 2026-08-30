"""Domain models. This layer imports nothing from other app/ layers."""
import datetime

from sqlalchemy import Column, DateTime, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    order_id = Column(String, unique=True, nullable=False)
    customer_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    total_amount = Column(Numeric(14, 2), nullable=False)
    region = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    __table_args__ = (
        Index("idx_orders_status_created_at", "status", text("created_at DESC")),
        Index("idx_orders_region_created_at", "region", text("created_at DESC")),
    )


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True)
    task_id = Column(String, unique=True, nullable=False)
    report_type = Column(String, nullable=False)
    params = Column(JSONB, nullable=False, default=dict)
    status = Column(String, nullable=False)
    result = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
