# Asynchronous E-Commerce Report Engine

> **Scope contract:** see [INTENT.md](./INTENT.md) — what this service must do and why.
> **Original brief:** see [ASSIGNMENT.md](./ASSIGNMENT.md).

## 1. What it is

A backend service that ingests high volumes of e-commerce order events and
generates heavy analytical reports **asynchronously**.

- Ingestion is fast and does no computation — it validates and bulk-inserts.
- Report generation is offloaded to background workers over a message queue,
  so a heavy aggregation never blocks an HTTP request.
- Dashboard reads are served from a Redis cache instead of being recomputed.

It is self-contained: order events come from your own services, reports go to
your own dashboards. No third-party services are called on the request or
worker path.

## 2. Architecture

Clean Architecture — each layer only talks to the one below it:

```
app/
├── api/            # FastAPI routers + Pydantic request/response schemas (no logic, no SQL)
├── core/           # config, database engine, Redis client, structured logger
├── domain/         # SQLAlchemy models and domain exceptions (imports nothing from app/)
├── repositories/   # the ONLY place SQLAlchemy queries are written
├── services/       # orchestration: repositories + cache + workers
└── workers/        # Celery tasks and broker configuration
```

**Request flow**

```
POST /events/batch ──▶ API (validate + bulk insert) ──▶ Postgres          [fast, no compute]

POST /reports/generate ──▶ API ──▶ RabbitMQ ──▶ Celery worker
                                                   │ aggregate in SQL
                                                   ▼
                                               Postgres (reports table)
                                                   │ retry w/ backoff, DLQ on permanent failure

GET /reports/{task_id} ──▶ API ──▶ Postgres (poll status + result)

GET /analytics/metrics ──▶ API ──▶ Redis (hit) │ Postgres (miss → cache w/ TTL)
```

## 3. API Reference

Base path: `/api/v1`

### `POST /api/v1/events/batch`
Ingest a batch of order events. Validates, bulk-inserts, returns immediately.
No computation.

**Headers**

| Header | Required | Purpose |
| --- | --- | --- |
| `Idempotency-Key` | yes | Replaying a batch with the same key is a no-op (no duplicate rows). |

**Request**

```json
{
  "events": [
    {
      "order_id": "ord_1001",
      "customer_id": "cus_42",
      "status": "paid",
      "total_amount": 129.90,
      "region": "EU",
      "created_at": "2026-08-30T10:15:00Z"
    }
  ]
}
```

**Response** — `202 Accepted`

```json
{ "status": "accepted", "ingested": 1, "duplicates": 0 }
```

### `POST /api/v1/reports/generate`
Dispatch a background aggregation job. Returns a `task_id` to poll.

**Request**

```json
{
  "report_type": "revenue_summary",
  "date_from": "2026-08-01",
  "date_to": "2026-08-31",
  "group_by": ["region", "status"]
}
```

**Response** — `202 Accepted`

```json
{ "task_id": "rpt_7f3a2c", "status": "PENDING" }
```

### `GET /api/v1/reports/{task_id}`
Poll one report resource.

**Response** — `200 OK`

```json
{
  "task_id": "rpt_7f3a2c",
  "status": "SUCCESS",
  "result": {
    "total_revenue": 184230.55,
    "order_count": 1920,
    "average_order_value": 95.95,
    "by_region": { "EU": 90120.00, "US": 71110.55, "APAC": 23000.00 },
    "by_day": [ { "day": "2026-08-01", "revenue": 6011.20 } ],
    "growth_vs_previous_period": 0.14
  }
}
```

`status` transitions: `PENDING → STARTED → SUCCESS`, or `→ FAILURE`, or
`→ DEAD_LETTER` (permanently failed after retries). `result` is `null` until
`SUCCESS`.

### `GET /api/v1/analytics/metrics`
Rolling summary (default: last 24 hours). Cache-Aside: served from Redis on a
hit; on a miss, aggregated from PostgreSQL and cached with a short TTL. The
cache is invalidated when new events are ingested.

**Response** — `200 OK`

```json
{
  "window": "24h",
  "revenue": 12043.10,
  "order_count": 138,
  "average_order_value": 87.27,
  "orders_by_region": { "EU": 61, "US": 55, "APAC": 22 }
}
```

### Errors
All endpoints return a consistent structure:

```json
{ "detail": [ { "loc": ["body", "events", 0, "total_amount"], "msg": "value must be >= 0", "type": "value_error" } ] }
```

## 4. Database

**`orders`** — `id`, `order_id` (unique), `customer_id`, `status`,
`total_amount`, `region`, `created_at`.

**`reports`** — `id`, `task_id` (unique), `report_type`, `params` (JSONB),
`status`, `result` (JSONB), `created_at`, `updated_at`.

**Indexes** — composite indexes on `orders` matching the report/analytics
query shape:

```sql
CREATE INDEX idx_orders_status_created_at ON orders (status, created_at DESC);
CREATE INDEX idx_orders_region_created_at ON orders (region, created_at DESC);
```

## 5. Run locally

```bash
docker-compose up --build
```

Starts API (`:8000`), Celery worker, PostgreSQL, Redis, RabbitMQ. Services are
healthcheck-gated and the schema is initialized before the API accepts traffic.

- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## 6. Run the tests

```bash
docker-compose run --rm api pytest -v --cov=app tests/
```

- **Unit** (`test_api.py`) — schema validation, the structured-error envelope,
  route delegation, and the ingestion service's idempotency + cache
  invalidation, all with the DB and Redis mocked.
- **Integration** (`test_integration.py`) — report aggregation SQL against a
  real PostgreSQL 16 via `testcontainers`. Skipped automatically when no
  Docker daemon is reachable.
- **Worker** (`test_workers.py`) — state transitions, deterministic re-run,
  and `DEAD_LETTER` routing via the task's `on_failure` handler.

## 7. Run the index benchmark

```bash
docker-compose exec db psql -U user -d analytics_db -f /database_migrations/explain_benchmark.sql
```

Seeds a large synthetic `orders` dataset and runs `EXPLAIN ANALYZE` on the
report query, showing the plan use an **Index Scan** rather than a
**Sequential Scan**.

## 8. Quality gates (CI)

On every push / PR: `ruff` (lint) + `mypy` (types) + `pytest` (tests + coverage).
Zero linter and zero typing errors required.
