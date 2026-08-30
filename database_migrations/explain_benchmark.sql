-- explain_benchmark.sql
-- Proves the report/analytics queries use an index-based access path
-- (Index Only Scan / Index Scan / Bitmap Index Scan) on idx_orders_created_at
-- instead of a Sequential Scan over the whole orders table.
--
-- The query shape here is the one the application actually issues
-- (SyncReportRepository.report_aggregates / OrderRepository.rolling_metrics):
-- a created_at range filter, then aggregate total_amount. No status/region
-- predicate -- those only appear in the GROUP BY breakdowns.
--
-- Run:  docker-compose exec db psql -U user -d analytics_db -f /database_migrations/explain_benchmark.sql

-- Seed a large synthetic dataset (~150k rows over 90 days) if the table is small.
INSERT INTO orders (id, order_id, customer_id, status, total_amount, region, created_at)
SELECT
    gen_random_uuid()::varchar,
    'ord_bench_' || g::text,
    'cus_' || (g % 5000)::text,
    (ARRAY['pending','paid','shipped','delivered','cancelled'])[1 + (g % 5)],
    round((random() * 500)::numeric, 2),
    (ARRAY['EU','US','APAC'])[1 + (g % 3)],
    NOW() - (random() * interval '90 days')
FROM generate_series(1, 150000) AS g
ON CONFLICT (order_id) DO NOTHING;

ANALYZE orders;

-- WITH the index: a ~2-day window out of 90 is ~2% of the table. The planner
-- should pick an index path on idx_orders_created_at (Index Only Scan, since
-- total_amount is INCLUDE'd).
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(id), coalesce(sum(total_amount), 0), coalesce(avg(total_amount), 0)
FROM orders
WHERE created_at >= NOW() - interval '2 days'
  AND created_at <= NOW();

-- Contrast: with the index dropped, the same query has no choice but a
-- Sequential Scan over every row.
BEGIN;
DROP INDEX idx_orders_created_at;
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(id), coalesce(sum(total_amount), 0), coalesce(avg(total_amount), 0)
FROM orders
WHERE created_at >= NOW() - interval '2 days'
  AND created_at <= NOW();
ROLLBACK;
