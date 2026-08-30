# Project Intent: Asynchronous E-Commerce Report Engine

## Business Goal
Provide a production-grade backend that ingests high volumes of e-commerce order
events and generates heavy analytical reports **asynchronously**, so that:

- The ingestion path stays fast and never blocks on computation.
- Expensive aggregations (revenue rollups, regional breakdowns, growth trends)
  run in background workers instead of inside an HTTP request.
- Repeated dashboard reads are served from cache, not recomputed against the
  database every time.

This is the "click Export, we build it, we tell you when it's ready" pattern:
a client asks for a report, the server accepts the job immediately, a worker
computes it, and the client polls until it is ready.

The engine is **self-contained**. Order events come from the business's own
services; reports go to the business's own dashboards. There are no third-party
services in the request or worker path.

## Core Workflows

### 1. High-Volume Ingestion — `POST /api/v1/events/batch`
Clients send batches of order events (order id, customer, status, amount,
region, timestamp). The endpoint validates the payload, performs a single bulk
insert into PostgreSQL, and returns `202 Accepted`. It performs **no
computation**. Ingestion is **idempotent**: replaying a batch with the same
`Idempotency-Key` header does not create duplicate rows.

### 2. Background Report Generation — `POST /api/v1/reports/generate`
Dispatches a heavy aggregation job (e.g. "revenue and order breakdown for a
date range") to a Celery worker via RabbitMQ. Returns `202 Accepted` with a
`task_id`. The worker computes the report **entirely from rows already in
PostgreSQL** — totals, breakdown by region/status/day, average order value,
period-over-period change — and writes the result back to the `reports` table.

### 3. Report Retrieval — `GET /api/v1/reports/{task_id}`
Polls one report resource. Returns the current `status`
(`PENDING → STARTED → SUCCESS → FAILURE → DEAD_LETTER`) and the computed
`result` payload once `status == SUCCESS` (`null` before then).

### 4. Live Analytics — `GET /api/v1/analytics/metrics`
Returns a rolling summary (e.g. last 24 hours: revenue, orders by region,
average order value). Read-heavy and dashboard-facing. Uses the **Cache-Aside
pattern**: read from Redis first; on a miss, aggregate from PostgreSQL, store in
Redis with a short TTL, and return. The cache entry is invalidated when new
events are ingested.

## Architectural Constraints & Guardrails

- **Clean Architecture.** Strict separation: API (FastAPI routers + schemas) →
  Services (orchestration) → Repositories (all SQLAlchemy queries) → Domain
  (models, exceptions). A schema change must not reach the routing layer.
- **Asynchronous stack.** `asyncio`, FastAPI, and async SQLAlchemy 2.0 with
  `asyncpg` for all I/O-bound work on the API side.
- **Self-contained computation.** Every background job must be reproducible from
  data already in PostgreSQL, must make **zero network calls outside
  `docker-compose.yml`**, and a retry must produce **byte-identical output**.
- **Deterministic aggregation in SQL.** Percentiles, rollups, and breakdowns are
  computed with SQL (`GROUP BY`, `percentile_cont`, window functions), not by
  pulling rows into Python. No new numeric/dataframe dependencies.
- **Resilience.** Background tasks implement exponential-backoff retries for
  transient failures and route permanently failed jobs to a Dead-Letter Queue
  without crashing the worker pipeline.
- **Job idempotency.** Re-executing a report job with the same `task_id`
  (via a retry or a duplicate dispatch) must not duplicate or corrupt the
  stored report. Because the computation is deterministic, a re-run overwrites
  with an identical result.
- **Query optimization, proven.** A composite index on `orders`
  (`(status, created_at DESC)` and/or `(region, created_at DESC)`) supports the
  report and analytics queries. A dedicated benchmark script runs
  `EXPLAIN ANALYZE` on a large synthetic dataset and demonstrates the query
  plan shifting from a **Sequential Scan** to an **Index Scan**.
- **Containerization.** API, worker, PostgreSQL, Redis, and RabbitMQ all start
  cleanly with a single `docker-compose up --build`, healthcheck-gated, with
  the schema initialized before the first request — no race conditions.

## Acceptance Criteria Checklist
(Mirrors `ASSIGNMENT.md` — every item there maps to one here.)

- [~] `docker-compose up --build` starts API, worker, database, cache, and
      broker cleanly without race conditions. *(compose + healthcheck-gated
      deps + `/docker-entrypoint-initdb.d` schema mount written; not yet run —
      no local Docker daemon.)*
- [x] Endpoints validate inputs strictly and return consistent structured error
      responses. *(Pydantic v2 + `RequestValidationError`/`HTTPException`
      handlers normalising to `{"detail": [...]}`.)*
- [x] `POST /api/v1/events/batch` persists batches with low latency and no
      on-the-fly computation; duplicate `Idempotency-Key` is a no-op.
      *(single `INSERT ... ON CONFLICT (order_id) DO NOTHING RETURNING`;
      batch-level replay short-circuits via a Redis marker.)*
- [x] `POST /api/v1/reports/generate` returns `202` + `task_id`;
      `GET /api/v1/reports/{task_id}` reports lifecycle states and returns the
      generated payload on success. *(API-generated `rpt_*` id; PENDING row
      written before dispatch.)*
- [x] Background report jobs reliably transition states and save results back to
      the database; a retry produces an identical result. *(deterministic SQL
      aggregation; `save_result` is an idempotent upsert keyed on `task_id`.)*
- [x] Permanently failed jobs are routed to a Dead-Letter Queue; the worker
      keeps running. *(`ReportTask.on_failure` → `DEAD_LETTER`;
      `on_retry` → `FAILURE`.)*
- [x] Caching reduces repeated query latency on `/api/v1/analytics/metrics`;
      the cache is invalidated on ingestion. *(Cache-Aside in
      `AnalyticsService`; `IngestionService` deletes the key after insert.)*
- [~] A benchmark script proves the composite index is used
      (`EXPLAIN ANALYZE`: Seq Scan → Index Scan) on a large dataset.
      *(`explain_benchmark.sql` seeds ~150k rows and contrasts the plan with
      the index dropped; not yet run — no local Docker daemon.)*
- [~] Unit, integration, and worker tests all pass locally and in CI with
      0 linter and 0 typing errors. *(unit + worker: 14 pass, ruff 0, mypy 0
      on a local py3.10 venv. Integration (`testcontainers`) skips without
      Docker — never executed. CI workflow added, not yet run.)*
