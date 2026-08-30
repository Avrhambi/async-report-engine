-- 001_initial_schema.sql
-- E-Commerce Report Engine schema. Runs at Postgres init via
-- /docker-entrypoint-initdb.d so the schema exists before the API starts.

CREATE TABLE IF NOT EXISTS orders (
    id            VARCHAR PRIMARY KEY,
    order_id      VARCHAR UNIQUE NOT NULL,
    customer_id   VARCHAR NOT NULL,
    status        VARCHAR NOT NULL,
    total_amount  NUMERIC(14, 2) NOT NULL,
    region        VARCHAR NOT NULL,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Composite indexes matching the report / analytics query shape:
-- filters lead with status or region, then scan a created_at range.
CREATE INDEX IF NOT EXISTS idx_orders_status_created_at ON orders (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_region_created_at ON orders (region, created_at DESC);

CREATE TABLE IF NOT EXISTS reports (
    id           VARCHAR PRIMARY KEY,
    task_id      VARCHAR UNIQUE NOT NULL,
    report_type  VARCHAR NOT NULL,
    params       JSONB NOT NULL DEFAULT '{}'::jsonb,
    status       VARCHAR NOT NULL,
    result       JSONB,
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_task_id ON reports (task_id);
