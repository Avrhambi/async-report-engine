"""Integration tests against a real PostgreSQL via testcontainers.

Skipped automatically when Docker is unavailable (e.g. some CI shells or a
dev box without a running daemon).
"""
from __future__ import annotations

import datetime
import os
from collections.abc import Iterator

import pytest
from app.domain.models import Base
from app.repositories.sync_report_repo import SyncReportRepository
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# When TEST_DATABASE_URL points at an already-running Postgres 16 (the
# docker-compose `db` service, or a CI `services: postgres`), use it directly
# and skip testcontainers entirely. This is how the suite runs inside the
# compose network, where testcontainers' default-bridge port publishing is
# unreachable. Otherwise fall back to spinning a throwaway container.
_EXTERNAL_DB_URL = os.getenv("TEST_DATABASE_URL")


@pytest.fixture(scope="module")
def pg_session() -> Iterator[Session]:
    container = None
    if _EXTERNAL_DB_URL:
        url = _EXTERNAL_DB_URL.replace("+asyncpg", "+psycopg").replace(
            "psycopg2", "psycopg"
        )
    else:
        tc_postgres = pytest.importorskip("testcontainers.postgres")
        container = tc_postgres.PostgresContainer("postgres:16")
        try:
            container.start()
        except Exception as exc:  # pragma: no cover - env-dependent
            # Only a genuine "no Docker daemon reachable" should skip. Any other
            # error (bad image, fixture bug) must surface as a failure.
            from docker.errors import DockerException
            from requests.exceptions import ConnectionError as RequestsConnectionError

            daemon_unreachable = (
                isinstance(
                    exc,
                    (DockerException, RequestsConnectionError, ConnectionError),
                )
                or "docker" in str(exc).lower()
            )
            if daemon_unreachable:
                pytest.skip(f"Docker unavailable: {exc}")
            raise
        url = container.get_connection_url().replace("psycopg2", "psycopg")

    engine = create_engine(url)
    # create_all emits the indexes declared in models.py __table_args__.
    Base.metadata.create_all(engine)

    maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = maker()
    if _EXTERNAL_DB_URL:
        # Shared DB may hold rows from a prior run; the assertions below are
        # exact counts against a module-scoped session, so start clean.
        session.execute(text("TRUNCATE orders"))
        session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        if container is not None:
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

    # created_at is seeded monotonically (5-min steps back from a fixed
    # anchor), so it is physically correlated with insert order and a narrow
    # range maps to a handful of heap pages -- the planner picks the index
    # even on a small table with the visibility map unset (no VACUUM here).
    # The window is anchored in 2027 so it can't perturb the Aug-2026
    # aggregation assertions in the tests above (module-scoped session).
    pg_session.execute(
        text(
            "INSERT INTO orders "
            "(id, order_id, customer_id, status, total_amount, region, created_at) "
            "SELECT gen_random_uuid()::varchar, 'ord_idx_' || g, 'cus_1', 'paid', "
            "round((random() * 100)::numeric, 2), 'EU', "
            "TIMESTAMPTZ '2027-06-01 00:00:00+00' - (g * interval '5 minutes') "
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
                "SELECT count(*), coalesce(sum(total_amount), 0) FROM orders "
                "WHERE created_at >= TIMESTAMPTZ '2027-05-30 00:00:00+00' "
                "AND created_at <= TIMESTAMPTZ '2027-06-01 00:00:00+00'"
            )
        ).all()
    )
    assert "idx_orders_created_at" in plan
    assert "Seq Scan" not in plan
