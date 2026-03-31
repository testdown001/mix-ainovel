-- Phase 4: Table partitioning for high-volume tables
-- Execute during a maintenance window after verifying data volumes.
-- Each section can be run independently.

-- ============================================================
-- 1. chapter_versions: RANGE partition by id (every 5M rows)
-- Prerequisite: ensure id is the primary key (no composite PK with other columns)
-- ============================================================

-- Check current row count first:
-- SELECT COUNT(*) FROM chapter_versions;

-- Only apply when approaching 5M rows:
/*
ALTER TABLE chapter_versions PARTITION BY RANGE (id) (
    PARTITION p0 VALUES LESS THAN (5000000),
    PARTITION p1 VALUES LESS THAN (10000000),
    PARTITION p2 VALUES LESS THAN (15000000),
    PARTITION p3 VALUES LESS THAN (20000000),
    PARTITION pmax VALUES LESS THAN MAXVALUE
);
*/

-- To add a new partition later (before MAXVALUE):
-- ALTER TABLE chapter_versions REORGANIZE PARTITION pmax INTO (
--     PARTITION p4 VALUES LESS THAN (25000000),
--     PARTITION pmax VALUES LESS THAN MAXVALUE
-- );


-- ============================================================
-- 2. payment_orders: RANGE partition by created_at (yearly)
-- Useful for archiving old payment records
-- ============================================================

/*
ALTER TABLE payment_orders PARTITION BY RANGE (UNIX_TIMESTAMP(created_at)) (
    PARTITION p2025 VALUES LESS THAN (UNIX_TIMESTAMP('2026-01-01')),
    PARTITION p2026 VALUES LESS THAN (UNIX_TIMESTAMP('2027-01-01')),
    PARTITION p2027 VALUES LESS THAN (UNIX_TIMESTAMP('2028-01-01')),
    PARTITION p2028 VALUES LESS THAN (UNIX_TIMESTAMP('2029-01-01')),
    PARTITION p2029 VALUES LESS THAN (UNIX_TIMESTAMP('2030-01-01')),
    PARTITION p2030 VALUES LESS THAN (UNIX_TIMESTAMP('2031-01-01')),
    PARTITION pmax VALUES LESS THAN MAXVALUE
);
*/


-- ============================================================
-- 3. writing_archives: RANGE partition by created_at (yearly)
-- Old archives can be dropped to reclaim space
-- ============================================================

/*
ALTER TABLE writing_archives PARTITION BY RANGE (UNIX_TIMESTAMP(created_at)) (
    PARTITION p2025 VALUES LESS THAN (UNIX_TIMESTAMP('2026-01-01')),
    PARTITION p2026 VALUES LESS THAN (UNIX_TIMESTAMP('2027-01-01')),
    PARTITION p2027 VALUES LESS THAN (UNIX_TIMESTAMP('2028-01-01')),
    PARTITION pmax VALUES LESS THAN MAXVALUE
);
*/

-- To drop an old partition (data is permanently removed):
-- ALTER TABLE writing_archives DROP PARTITION p2025;


-- ============================================================
-- 4. Additional index optimizations
-- ============================================================

-- payment_orders: composite index for user order history queries
CREATE INDEX IF NOT EXISTS idx_payment_orders_user_created
    ON payment_orders (user_id, created_at DESC);

-- subscriptions: fast lookup for expiration checks
CREATE INDEX IF NOT EXISTS idx_subscriptions_period_end
    ON subscriptions (current_period_end, status);

-- chapters: speed up project chapter listing
CREATE INDEX IF NOT EXISTS idx_chapters_project_number
    ON chapters (project_id, chapter_number);

-- foreshadowings: speed up per-project status queries
CREATE INDEX IF NOT EXISTS idx_foreshadowings_project_status
    ON foreshadowings (project_id, status, chapter_number);

-- chapter_outlines: unique per project+chapter
CREATE UNIQUE INDEX IF NOT EXISTS idx_chapter_outlines_project_chapter
    ON chapter_outlines (project_id, chapter_number);
