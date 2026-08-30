"""All SQLAlchemy queries against the orders table live here."""
from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Order


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_insert_ignore_duplicates(
        self, events: list[dict[str, Any]]
    ) -> int:
        """Single bulk INSERT ... ON CONFLICT (order_id) DO NOTHING.

        Returns the number of rows actually inserted (new orders); the
        caller derives the duplicate count from the batch size.
        """
        if not events:
            return 0

        rows = [
            {
                "id": str(uuid.uuid4()),
                "order_id": e["order_id"],
                "customer_id": e["customer_id"],
                "status": e["status"],
                "total_amount": e["total_amount"],
                "region": e["region"],
                "created_at": e["created_at"],
            }
            for e in events
        ]
        stmt = (
            pg_insert(Order)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["order_id"])
            .returning(Order.order_id)
        )
        result = await self.session.execute(stmt)
        inserted = len(result.scalars().all())
        await self.session.commit()
        return inserted

    async def report_aggregates(
        self,
        date_from: datetime.date,
        date_to: datetime.date,
        group_by: list[str],
    ) -> dict[str, Any]:
        """Compute the report payload entirely in SQL.

        Deterministic: same rows + same params -> byte-identical output.
        """
        upper = datetime.datetime.combine(
            date_to, datetime.time.max, tzinfo=datetime.timezone.utc
        )
        lower = datetime.datetime.combine(
            date_from, datetime.time.min, tzinfo=datetime.timezone.utc
        )
        window = (Order.created_at >= lower) & (Order.created_at <= upper)

        totals_stmt = select(
            func.coalesce(func.sum(Order.total_amount), 0).label("total_revenue"),
            func.count(Order.id).label("order_count"),
            func.coalesce(func.avg(Order.total_amount), 0).label("aov"),
        ).where(window)
        totals = (await self.session.execute(totals_stmt)).one()

        breakdowns: dict[str, dict[str, float]] = {}
        for field in group_by:
            col = {"region": Order.region, "status": Order.status}.get(field)
            if col is None:
                continue
            stmt = (
                select(col, func.coalesce(func.sum(Order.total_amount), 0))
                .where(window)
                .group_by(col)
                .order_by(col)
            )
            breakdowns[field] = {
                str(k): float(v) for k, v in (await self.session.execute(stmt)).all()
            }

        by_day_stmt = (
            select(
                func.date_trunc("day", Order.created_at).label("day"),
                func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
            )
            .where(window)
            .group_by(text("day"))
            .order_by(text("day"))
        )
        by_day = [
            {"day": day.date().isoformat(), "revenue": float(revenue)}
            for day, revenue in (await self.session.execute(by_day_stmt)).all()
        ]

        # Period-over-period: same-length window immediately before this one.
        span = upper - lower
        prev_stmt = select(
            func.coalesce(func.sum(Order.total_amount), 0)
        ).where(
            (Order.created_at >= lower - span) & (Order.created_at < lower)
        )
        prev_revenue = float((await self.session.execute(prev_stmt)).scalar_one())
        current_revenue = float(totals.total_revenue)
        if prev_revenue > 0:
            growth = round((current_revenue - prev_revenue) / prev_revenue, 4)
        else:
            growth = None

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

    async def rolling_metrics(self, window_hours: int = 24) -> dict[str, Any]:
        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            hours=window_hours
        )
        window = Order.created_at >= since

        totals_stmt = select(
            func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
            func.count(Order.id).label("order_count"),
            func.coalesce(func.avg(Order.total_amount), 0).label("aov"),
        ).where(window)
        totals = (await self.session.execute(totals_stmt)).one()

        region_stmt = (
            select(Order.region, func.count(Order.id))
            .where(window)
            .group_by(Order.region)
            .order_by(Order.region)
        )
        by_region = {
            str(r): int(c) for r, c in (await self.session.execute(region_stmt)).all()
        }

        return {
            "window": f"{window_hours}h",
            "revenue": round(float(totals.revenue), 2),
            "order_count": int(totals.order_count),
            "average_order_value": round(float(totals.aov), 2),
            "orders_by_region": by_region,
        }
