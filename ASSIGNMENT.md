# 🚀 Capstone Project Specification: Event-Driven Analytics & Report Processing Engine

## 1. Project Overview

Build a production-ready asynchronous backend service: an **Event Analytics & Asynchronous Report Aggregator Engine**. This service ingests high-volume telemetry/event payloads, processes heavy analytical aggregations asynchronously, caches frequent reads, and exposes structured query APIs with verified database index execution plans.
---

## 2. Technical Stack & Architecture

| Component | Technology | Responsibility |
| --- | --- | --- |
| **API Framework** | **FastAPI** (Python 3.11+) | Async endpoints, Pydantic v2 schemas, Dependency Injection, Clean Architecture |
| **Database** | **PostgreSQL 16** + **SQLAlchemy 2.0 (Async)** | ACID transactions, strict schema constraints, targeted B-Tree/Composite indexing |
| **Cache Layer** | **Redis** | Cache-Aside pattern for hot analytical queries with TTL and cache invalidation |
| **Message Broker & Workers** | **RabbitMQ** + **Celery** | Heavy background task processing, automated retries, Dead-Letter Queue (DLQ) |
| **Testing Suite** | **Pytest** + **pytest-asyncio** + **Testcontainers / SQLite/PG test harness** | Unit, integration, and asynchronous E2E endpoint tests |
| **DevOps & Observability** | **Docker Compose**, **Ruff**, **Mypy**, **GitHub Actions**, **structlog** | Multi-stage Docker builds, strict linting, type safety, structured logging |

---

## 3. Core Requirements & Functional Capabilities

### A. API Layer & Clean Architecture (FastAPI)

* **Hexagonal / Clean Architecture Folder Structure:**
```text
app/
├── api/              # Routers, schemas (Pydantic v2), request/response models
├── core/             # Config (pydantic-settings), security, structured logger
├── domain/           # Business logic, entities, domain exceptions
├── repositories/     # Database access layer (SQLAlchemy async queries)
├── services/         # Orchestration layer (connecting repositories, cache, workers)
├── workers/          # Celery tasks and RabbitMQ configuration
└── tests/            # Pytest test suite (fixtures, integration tests, unit tests)
```

* **Endpoints:**
* `POST /api/v1/events/batch`: Ingests event batches asynchronously using FastAPI dependency-injected database sessions.
* `POST /api/v1/reports/generate`: Dispatches background aggregation tasks to Celery/RabbitMQ, returning `202 Accepted` with a `task_id`.
* `GET /api/v1/reports/{task_id}`: Polls task status and retrieves the generated analytical payload.
* `GET /api/v1/analytics/metrics`: Fetches aggregated metrics with **Cache-Aside pattern via Redis** (reads from Redis first; falls back to DB and sets TTL).



---

### B. Database & Query Optimization (PostgreSQL)

* **Schema Design:**
* `events` table (e.g., `id`, `user_id`, `event_type`, `payload (JSONB)`, `created_at`).
* `reports` table (e.g., `id`, `status`, `result_summary`, `created_at`, `updated_at`).


* **Indexing & EXPLAIN Verification:**
* Define a composite index (e.g., `CREATE INDEX idx_events_type_created_at ON events (event_type, created_at DESC);`).
* Include a dedicated SQL migration / verification script running `EXPLAIN (ANALYZE, BUFFERS)` to prove query plan shifts from `Seq Scan` to `Bitmap Index Scan` / `Index Only Scan`.



---

### C. Background Task Pipeline (Celery + RabbitMQ)

* **Asynchronous Processing:**
* Celery worker calculates aggregation metrics (e.g., event frequency, breakdown by user/type) and stores the result in PostgreSQL.


* **Resilience & Fault Tolerance:**
* Configured retry strategy with exponential backoff (`autoretry_for=(Exception,)`, `max_retries=3`).
* Idempotency handling to ensure repeated executions with the same `task_id` do not create duplicate state or corrupt analytics.



---

### D. Testing, Quality Assurance & CI/CD

* **Testing Suite (`pytest`):**
* **Unit Tests:** Domain logic and schema validations.
* **Integration Tests:** Async API endpoints with isolated test database instances (`pytest-asyncio`, `httpx.AsyncClient`).
* **Worker Tests:** Mocked/eager Celery worker execution to verify task lifecycle (`SUCCESS`, `RETRY`, `FAILURE`).


* **CI Pipeline (`.github/workflows/ci.yml`):**
* Automated execution of `ruff check`, `mypy --strict`, and `pytest` with code coverage reports on every push/PR.


* **Containerization:**
* Production-grade **Multi-stage `Dockerfile**` (non-root user, minimal final image).
* `docker-compose.yml` spinning up `web (FastAPI)`, `worker (Celery)`, `db (Postgres)`, `redis`, and `rabbitmq`.



---

## 4. Acceptance Criteria Checklist

* [x] `docker-compose up --build` starts the complete environment (`api`, `worker`, `postgres`, `redis`, `rabbitmq`) cleanly without race conditions.
* [x] Endpoints validate inputs via Pydantic v2 and return consistent structured error responses.
* [x] Redis caching layer reduces repeated query response latency on `/api/v1/analytics/metrics`.
* [x] Celery tasks reliably transition states (`PENDING` -> `STARTED` -> `SUCCESS`/`FAILURE`) and save results back to PostgreSQL.
* [x] A dedicated `explain_benchmark.sql` or test script validates the index performance using `EXPLAIN ANALYZE`.
* [x] All tests pass locally and in the GitHub Actions CI workflow with 0 linter (`ruff`) or typing (`mypy`) errors.
