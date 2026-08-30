"""Integration tests against a real PostgreSQL via testcontainers.

Skipped automatically when Docker is unavailable (e.g. some CI shells or a
dev box without a running daemon).
"""
from __future__ import annotations

import datetime
from collections.abc import Iterator

import pytest

testcontainers = pytest.importorskip("testcontainers.postgres")

from app.domain.models import Base  # noqa: E402
from app.repositories.sync_report_repo import SyncReportRepository  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402


@pytest.fixture(scope="module")
def pg_session() -> Iterator[Session]:
    try:
        container = testcontainers.postgres.PostgresContainer("postgres:16")
        container.start()
    except Exception as exc:  # pragma: no cover - env-dependent
        pytest.skip(f"Docker unavailable: {exc}")

    url = container.get_connection_url().replace("psycopg2", "psycopg")
    engine = create_engine(url)
    # create_all emits the indexes declared in models.py __table_args__.
    Base.metadata.create_all(engine)

    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        container.stop()


def _order(order_id: str, status: str, region: str, amount: str, day: str) -> dict:
    return {
        "id": order_id,
        "order_id": order_id,
        "customer_id": "cus_1",
        "status": status,
        "total_amount": amount,
        "region": region,
        "created_at": datetime.datetime.fromisoformat(day),
    }


def test_report_aggregates_are_computed_in_sql(pg_session: Session):
    from app.domain.models import Order

    pg_session.execute(
        Order.__table__.insert(),
        [
            _order("o1", "paid", "EU", "100.00", "2026-08-01T10:00:00+00:00"),
            _order("o2", "paid", "US", "50.00", "2026-08-01T12:00:00+00:00"),
            _order("o3", "cancelled", "EU", "30.00", "2026-08-02T09:00:00+00:00"),
        ],
    )
    pg_session.commit()

    repo = SyncReportRepository(pg_session)
    result = repo.report_aggregates(
        datetime.date(2026, 8, 1), datetime.date(2026, 8, 31), ["region", "status"]
    )

    assert result["order_count"] == 3
    assert result["total_revenue"] == 180.0
    assert result["average_order_value"] == 60.0
    assert result["by_region"] == {"EU": 130.0, "US": 50.0}
    assert result["by_status"] == {"cancelled": 30.0, "paid": 150.0}
    assert {row["day"] for row in result["by_day"]} == {"2026-08-01", "2026-08-02"}


def test_rerun_produces_identical_output(pg_session: Session):
    repo = SyncReportRepository(pg_session)
    args = (datetime.date(2026, 8, 1), datetime.date(2026, 8, 31), ["region"])
    assert repo.report_aggregates(*args) == repo.report_aggregates(*args)


def test_report_query_uses_created_at_index_not_seq_scan(pg_session: Session):
    """The report predicate (created_at range + sum/avg total_amount) must use
    an index-based access path, not a Sequential Scan over the heap."""
    from sqlalchemy import text

    pg_session.execute(
        text(
            "INSERT INTO orders "
            "(id, order_id, customer_id, status, total_amount, region, created_at) "
            "SELECT gen_random_uuid()::varchar, 'ord_idx_' || g, 'cus_1', 'paid', "
            "round((random() * 100)::numeric, 2), 'EU', "
            "NOW() - (random() * interval '90 days') "
            "FROM generate_series(1, 20000) AS g "
            "ON CONFLICT (order_id) DO NOTHING"
        )
    )
    pg_session.execute(text("ANALYZE orders"))
    pg_session.commit()

    plan = "\n".join(
        row[0]
        for row in pg_session.execute(
            text(
                "EXPLAIN "
                "SELECT count(id), coalesce(sum(total_amount), 0) FROM orders "
                "WHERE created_at >= NOW() - interval '2 days' "
                "AND created_at <= NOW()"
            )
        ).all()
    )
    assert "idx_orders_created_at" in plan
    assert "Seq Scan" not in plan
