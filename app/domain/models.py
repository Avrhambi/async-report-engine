from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)  # Using JSONB for efficient querying in Postgres
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # The requirements specifically asked for this composite index to optimize queries
    __table_args__ = (
        Index("idx_events_type_created_at", "event_type", created_at.desc()),
    )

class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True) # We will use the Celery task_id as the primary key
    status = Column(String, nullable=False, default="PENDING")
    result_summary = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
