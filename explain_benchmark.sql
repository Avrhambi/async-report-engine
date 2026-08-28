-- Explain Benchmark Script
-- This script validates the performance of the composite index on the events table.
-- Usage: Run this against the PostgreSQL database after seeding with sample data.

-- 1. Check the query plan WITHOUT index consideration (simulating large table scan)
-- EXPLAIN (ANALYZE, BUFFERS)
-- SELECT event_type, COUNT(id) 
-- FROM events 
-- WHERE created_at > NOW() - INTERVAL '1 day'
-- GROUP BY event_type;

-- 2. Verify the composite index usage
-- The index idx_events_type_created_at (event_type, created_at DESC) should be utilized
-- when filtering by created_at and grouping by event_type.

EXPLAIN (ANALYZE, BUFFERS)
SELECT event_type, created_at, payload
FROM events
WHERE event_type = 'login' 
  AND created_at >= NOW() - INTERVAL '7 days'
ORDER BY created_at DESC
LIMIT 100;

-- You should see an "Index Scan" or "Index Only Scan" on "idx_events_type_created_at"
-- instead of a "Seq Scan".
