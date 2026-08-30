"""Synchronous repository used only by the Celery worker path.

Mirrors the SQL of order_repo/report_repo but on a blocking Session, so the
worker never touches an event loop.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domain.models import Order, Report


class SyncReportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # -- reports table ------------------------------------------------------
    def get_by_task_id(self, task_id: str) -> Report | None:
        return self.session.execute(
            select(Report).where(Report.task_id == task_id)
        ).scalar_one_or_none()

    def set_status(self, task_id: str, status: str) -> None:
        report = self.get_by_task_id(task_id)
        if report is not None:
            report.status = status
            report.updated_at = datetime.datetime.now(datetime.timezone.utc)
            self.session.commit()

    def save_result(
        self,
        task_id: str,
        report_type: str,
        params: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
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
        self.session.execute(stmt)
        self.session.commit()

    # -- orders aggregation (deterministic, all in SQL) -------------------
    def report_aggregates(
        self,
        date_from: datetime.date,
        date_to: datetime.date,
        group_by: list[str],
    ) -> dict[str, Any]:
        lower = datetime.datetime.combine(
            date_from, datetime.time.min, tzinfo=datetime.timezone.utc
        )
        upper = datetime.datetime.combine(
            date_to, datetime.time.max, tzinfo=datetime.timezone.utc
        )
        window = (Order.created_at >= lower) & (Order.created_at <= upper)

        totals = self.session.execute(
            select(
                func.coalesce(func.sum(Order.total_amount), 0).label("total_revenue"),
                func.count(Order.id).label("order_count"),
                func.coalesce(func.avg(Order.total_amount), 0).label("aov"),
            ).where(window)
        ).one()

        breakdowns: dict[str, dict[str, float]] = {}
        for field in group_by:
            col = {"region": Order.region, "status": Order.status}.get(field)
            if col is None:
                continue
            rows = self.session.execute(
                select(col, func.coalesce(func.sum(Order.total_amount), 0))
                .where(window)
                .group_by(col)
                .order_by(col)
            ).all()
            breakdowns[field] = {str(k): float(v) for k, v in rows}

        by_day_rows = self.session.execute(
            select(
                func.date_trunc("day", Order.created_at).label("day"),
                func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
            )
            .where(window)
            .group_by(text("day"))
            .order_by(text("day"))
        ).all()
        by_day = [
            {"day": day.date().isoformat(), "revenue": float(revenue)}
            for day, revenue in by_day_rows
        ]

        span = upper - lower
        prev_revenue = float(
            self.session.execute(
                select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                    (Order.created_at >= lower - span) & (Order.created_at < lower)
                )
            ).scalar_one()
        )
        current_revenue = float(totals.total_revenue)
        growth = (
            round((current_revenue - prev_revenue) / prev_revenue, 4)
            if prev_revenue > 0
            else None
        )

        payload: dict[str, Any] = {
            "total_revenue": round(current_revenue, 2),
            "order_count": int(totals.order_count),
            "average_order_value": round(float(totals.aov), 2),
            "by_day": by_day,
            "growth_vs_previous_period": growth,
        }
        for field, data in breakdowns.items():
            payload[f"by_{field}"] = data
        return payload
