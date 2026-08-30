-- explain_benchmark.sql
-- Proves the composite index idx_orders_status_created_at is used for the
-- report query shape (filter on status, then a created_at range) instead of
-- a Sequential Scan.
--
-- Run:  docker-compose exec db psql -U user -d analytics_db -f /database_migrations/explain_benchmark.sql

-- Seed a large synthetic dataset (~150k rows) if the table is small.
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

-- Force a fair comparison: this query matches the composite index's leading
-- column (status) plus a created_at range.
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(id), coalesce(sum(total_amount), 0), coalesce(avg(total_amount), 0)
FROM orders
WHERE status = 'paid'
  AND created_at >= NOW() - interval '7 days';

-- Contrast: with the index dropped, the same query falls back to a Seq Scan.
BEGIN;
DROP INDEX idx_orders_status_created_at;
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(id), coalesce(sum(total_amount), 0), coalesce(avg(total_amount), 0)
FROM orders
WHERE status = 'paid'
  AND created_at >= NOW() - interval '7 days';
ROLLBACK;
