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

-- The report and analytics queries filter orders by a created_at range and
-- then aggregate total_amount. INCLUDE (total_amount) lets count/sum/avg be
-- answered from the index alone (Index Only Scan), so the query never falls
-- back to a Sequential Scan of the heap.
CREATE INDEX IF NOT EXISTS idx_orders_created_at
    ON orders (created_at DESC) INCLUDE (total_amount);

-- Composite indexes kept to match the documented contract (INTENT.md names
-- them by hand) and to back the GROUP BY region / GROUP BY status breakdowns.
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
