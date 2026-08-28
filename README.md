# Event-Driven Analytics & Report Processing Engine

An asynchronous backend service designed to ingest high-volume telemetry/event payloads, process heavy analytical aggregations asynchronously, cache frequent reads, and expose structured query APIs.

## Technical Stack & Architecture

| Component | Technology | Responsibility |
| --- | --- | --- |
| **API Framework** | **FastAPI** (Python 3.11+) | Async endpoints, Pydantic v2 schemas, Dependency Injection, Clean Architecture |
| **Database** | **PostgreSQL 16** + **SQLAlchemy 2.0 (Async)** | ACID transactions, strict schema constraints, targeted B-Tree/Composite indexing |
| **Cache Layer** | **Redis** | Cache-Aside pattern for hot analytical queries with TTL and cache invalidation |
| **Message Broker & Workers** | **RabbitMQ** + **Celery** | Heavy background task processing, automated retries, Dead-Letter Queue (DLQ) |
| **Testing Suite** | **Pytest** + **pytest-asyncio** + **Testcontainers / SQLite/PG test harness** | Unit, integration, and asynchronous E2E endpoint tests |
| **DevOps & Observability** | **Docker Compose**, **Ruff**, **Mypy**, **GitHub Actions**, **structlog** | Multi-stage Docker builds, strict linting, type safety, structured logging |

## Folder Architecture

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

## Running Locally

To spin up the complete environment (API, Worker, Postgres, Redis, RabbitMQ):

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`.

## Documentation & Instructions

For the original project specifications, technical stack details, and acceptance criteria, please refer to the [ASSIGNMENT.md](./ASSIGNMENT.md) file.
