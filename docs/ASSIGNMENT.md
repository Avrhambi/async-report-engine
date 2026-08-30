# Capstone Assignment: Event-Driven Analytics & Report Processing Engine

## Objective
Design and implement a robust, event-driven backend service capable of ingesting high volumes of telemetry data, processing heavy analytical tasks asynchronously, and serving fast, optimized queries to clients.

## Core Prescriptions and Requirements

In this assignment requires you to fulfill the following architectural and functional capabilities:

### 1. Architectural Separation
* **Clean Architecture:** You must adopt a strictly layered architecture. Your web API routing, business logic, data access (database queries), and background workers must be decoupled. Changes in the database schema should not directly break your API routing layer.

### 2. High-Volume Data Ingestion
* **Responsive API:** Implement an ingestion endpoint designed to accept large batches of event data.
* **Non-Blocking:** This endpoint must validate the incoming payload and persist it immediately while maintaining extremely low latency. It should not perform heavy computations on the fly.

### 3. Asynchronous Background Processing
* **Task Offloading:** Heavy computational tasks (such as evaluating data, running toxicity checks, or aggregating analytical reports) must be offloaded to a background worker ecosystem.
* **Message Brokering:** Use a message queue to dispatch these tasks reliably from the web API to the background workers.

### 4. Data Storage & Query Optimization
* **Relational Storage:** Design a normalized database schema to store incoming events and generated reports.
* **Optimized Queries:** You must implement targeted database indexing (e.g., composite indexes) to ensure that querying large datasets is highly efficient. You are expected to prove that your queries use indexes rather than falling back to slow, sequential table scans.

### 5. Caching Strategy
* **Cache-Aside Pattern:** Implement a caching layer for read-heavy analytical endpoints. 
* **Reduced Database Load:** When a client requests performance metrics or reports, the system should serve the response directly from the cache if available, falling back to the database only when the cache is empty or expired.

### 6. Resilience & Fault Tolerance
* **Retry Mechanisms:** Background tasks are prone to intermittent failures. You must implement a retry strategy (e.g., exponential backoff) for your background jobs.
* **Idempotency:** Ensure that if a job is executed multiple times (due to a retry), it does not corrupt the data or create duplicate states.
* **Dead-Letter Handling:** The system must be able to gracefully set aside permanently failed tasks without crashing the worker pipeline.

### 7. Automated Quality Assurance & DevOps
* **Comprehensive Testing:** Develop an automated test suite covering both unit tests (for business logic) and integration tests (for API endpoints and database operations).
* **Containerization:** The entire application ecosystem (web server, database, cache, message broker, and workers) must be fully containerized so that it can be spun up deterministically using a single orchestration command, with no race conditions between the services.

## Acceptance Criteria Checklist

* [ ] Orchestration command (e.g., `docker-compose up --build`) starts the complete environment (API, worker, database, cache, broker) cleanly without race conditions.
* [ ] Endpoints validate inputs strictly and return consistent structured error responses.
* [ ] Caching layer reduces repeated query response latency on `/api/v1/<service_name>`.
* [ ] Background tasks reliably transition states and save results back to the database.
* [ ] A dedicated benchmark script validates the index performance using a query plan analyzer.
* [ ] All tests pass locally and in the CI workflow with 0 linter or typing errors.