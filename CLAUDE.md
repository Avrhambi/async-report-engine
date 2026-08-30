# AI Agent Knowledge Base (CLAUDE.md)

## Repository Structure & Clean Architecture Rules
This project strictly follows Clean Architecture principles:
- **`app/api/`**: FastAPI routers and Pydantic schemas. **Rule:** No business logic or database queries allowed here. Route handlers must immediately delegate to the `app/services/` layer.
- **`app/services/`**: Orchestration and business logic. **Rule:** This layer connects repositories, caches, and Celery workers.
- **`app/repositories/`**: Database access layer. **Rule:** The only place where `SQLAlchemy` queries are executed.
- **`app/domain/`**: Database models and domain exceptions. **Rule:** Must not import from other `app/` layers.
- **`app/workers/`**: Celery tasks and configuration.
- **`app/core/`**: Centralized configuration (`pydantic-settings`), DB setup, and Redis singletons.

## Tech Stack & Conventions
- **Python**: 3.11+
- **Framework**: FastAPI (Async)
- **Database**: PostgreSQL 16 via async SQLAlchemy 2.0
- **Cache**: Redis (Async client)
- **Workers**: Celery with RabbitMQ broker
- **Testing**: `pytest` and `pytest-asyncio`

## How to Run the Project
**Start Infrastructure (Local Dev):**
```bash
docker-compose up --build
```

**Run Tests:**
```bash
docker-compose run --rm api pytest -v --cov=app tests/
```

## Structural Guardrails
- Always use `Idempotency-Key` headers for `POST` ingestion routes to prevent duplicate processing.
- Caching logic must use the Cache-Aside pattern (check Redis first, if miss -> check Postgres -> save to Redis -> return).
- Background tasks (`@celery.task`) must implement `autoretry_for=(Exception,)` with exponential backoff.
