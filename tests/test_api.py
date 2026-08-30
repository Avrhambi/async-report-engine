"""API-layer tests: input validation, error envelope, and route wiring
(services mocked). Integration against a real DB lives in test_integration.py.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from app.api import routes
from app.domain.exceptions import ReportNotFoundError

VALID_EVENT = {
    "order_id": "ord_1001",
    "customer_id": "cus_42",
    "status": "paid",
    "total_amount": 129.90,
    "region": "EU",
    "created_at": "2026-08-30T10:15:00Z",
}


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_events_batch_requires_idempotency_key(client):
    resp = client.post("/api/v1/events/batch", json={"events": [VALID_EVENT]})
    assert resp.status_code == 422
    assert isinstance(resp.json()["detail"], list)


def test_events_batch_rejects_negative_amount(client):
    bad = {**VALID_EVENT, "total_amount": -5}
    resp = client.post(
        "/api/v1/events/batch",
        json={"events": [bad]},
        headers={"Idempotency-Key": "k1"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"][0]["loc"][-1] == "total_amount"


def test_events_batch_rejects_bad_timestamp(client):
    bad = {**VALID_EVENT, "created_at": "not-a-date"}
    resp = client.post(
        "/api/v1/events/batch",
        json={"events": [bad]},
        headers={"Idempotency-Key": "k1"},
    )
    assert resp.status_code == 422
    assert isinstance(resp.json()["detail"], list)


def test_events_batch_accepts_and_delegates(client, monkeypatch):
    mock = AsyncMock(
        return_value={"status": "accepted", "ingested": 1, "duplicates": 0}
    )
    monkeypatch.setattr(routes.IngestionService, "ingest_batch", mock)

    resp = client.post(
        "/api/v1/events/batch",
        json={"events": [VALID_EVENT]},
        headers={"Idempotency-Key": "k1"},
    )
    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted", "ingested": 1, "duplicates": 0}
    assert mock.await_args.args[0] == "k1"


@pytest.mark.asyncio
async def test_analytics_loser_serves_cache_without_second_query(fake_redis):
    import asyncio

    from app.services.analytics_service import AnalyticsService

    repo = AsyncMock()
    repo.rolling_metrics.return_value = {
        "window": "24h",
        "revenue": 1.0,
        "order_count": 1,
        "average_order_value": 1.0,
        "orders_by_region": {"EU": 1},
    }
    svc = AnalyticsService(repo, fake_redis)

    await asyncio.gather(svc.get_metrics(), svc.get_metrics())

    # Single-flight: the second concurrent miss waited and read the cache.
    assert repo.rolling_metrics.await_count == 1


def test_generate_report_returns_task_id(client, monkeypatch):
    monkeypatch.setattr(
        routes.ReportService,
        "dispatch",
        AsyncMock(return_value={"task_id": "rpt_abc123", "status": "PENDING"}),
    )
    resp = client.post(
        "/api/v1/reports/generate",
        json={
            "report_type": "revenue_summary",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
            "group_by": ["region", "status"],
        },
    )
    assert resp.status_code == 202
    assert resp.json() == {"task_id": "rpt_abc123", "status": "PENDING"}


def test_generate_report_rejects_reversed_date_range(client):
    resp = client.post(
        "/api/v1/reports/generate",
        json={
            "report_type": "revenue_summary",
            "date_from": "2026-08-31",
            "date_to": "2026-08-01",
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert isinstance(body["detail"], list)
    assert "date_to must not be earlier than date_from" in body["detail"][0]["msg"]


def test_get_report_unknown_task_id_is_structured_404(client, monkeypatch):
    monkeypatch.setattr(
        routes.ReportService,
        "get",
        AsyncMock(side_effect=ReportNotFoundError("rpt_missing")),
    )
    resp = client.get("/api/v1/reports/rpt_missing")
    assert resp.status_code == 404
    assert isinstance(resp.json()["detail"], list)
    assert resp.json()["detail"][0]["type"] == "error"


def test_analytics_metrics_shape(client, monkeypatch):
    monkeypatch.setattr(
        routes.AnalyticsService,
        "get_metrics",
        AsyncMock(
            return_value={
                "window": "24h",
                "revenue": 12043.10,
                "order_count": 138,
                "average_order_value": 87.27,
                "orders_by_region": {"EU": 61, "US": 55, "APAC": 22},
            }
        ),
    )
    resp = client.get("/api/v1/analytics/metrics")
    assert resp.status_code == 200
    assert resp.json()["window"] == "24h"
    assert resp.json()["orders_by_region"]["EU"] == 61


@pytest.mark.asyncio
async def test_ingestion_service_invalidates_cache_and_counts_duplicates(fake_redis):
    from app.services.analytics_service import ANALYTICS_CACHE_KEY
    from app.services.ingestion_service import IngestionService

    fake_redis.store[ANALYTICS_CACHE_KEY] = "stale"
    repo = AsyncMock()
    repo.bulk_insert_ignore_duplicates.return_value = 2
    svc = IngestionService(repo, fake_redis)

    events = [VALID_EVENT, VALID_EVENT, VALID_EVENT]
    result = await svc.ingest_batch("batch-1", events)

    assert result == {"status": "accepted", "ingested": 2, "duplicates": 1}
    assert ANALYTICS_CACHE_KEY not in fake_redis.store

    # Full replay of the same key is a no-op.
    replay = await svc.ingest_batch("batch-1", events)
    assert replay == {"status": "accepted", "ingested": 0, "duplicates": 3}
