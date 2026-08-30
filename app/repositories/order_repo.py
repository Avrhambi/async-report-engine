"""Async SQLAlchemy queries against the orders table (API side).

The report aggregation SQL lives in sync_report_repo.py (worker side) so the
determinism guarantee has a single implementation.
"""
from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import func, select
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

        ON CONFLICT resolves collisions against *stored* rows only -- two rows
        with the same order_id in one INSERT raise "cannot affect row a second
        time". So we dedup the batch by order_id first (last occurrence wins),
        leaving the statement only unique targets.
        """
        if not events:
            return 0

        deduped = list({e["order_id"]: e for e in events}.values())

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
            for e in deduped
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

    async def rolling_metrics(self, window_hours: int = 24) -> dict[str, Any]:
        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            hours=window_hours
        )
        window = Order.created_at >= since

        # count() -> count(*): keeps every column in this query inside
        # idx_orders_created_at (key: created_at, INCLUDE: total_amount) so
        # the totals come from an Index Only Scan.
        totals_stmt = select(
            func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
            func.count().label("order_count"),
            func.coalesce(func.avg(Order.total_amount), 0).label("aov"),
        ).where(window)
        totals = (await self.session.execute(totals_stmt)).one()

        region_stmt = (
            select(Order.region, func.count())
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
