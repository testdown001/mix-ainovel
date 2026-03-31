-- Phase 1: Index optimization for high-volume tables
-- Run against the production MySQL database

-- chapter_versions: avoid full-scan for "latest version" queries
CREATE INDEX IF NOT EXISTS idx_chapter_versions_chapter_version
    ON chapter_versions (chapter_id, version_label);

-- character_states: speed up per-character-per-chapter lookups
-- (check if character_states table exists first)
-- CREATE INDEX IF NOT EXISTS idx_character_states_project_char_chapter
--     ON character_states (project_id, character_id, chapter_number);

-- foreshadowings: speed up active foreshadowing queries
-- CREATE INDEX IF NOT EXISTS idx_foreshadowings_project_status_chapter
--     ON foreshadowings (project_id, status, chapter_number);

-- chapter_outlines: ensure unique constraint
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_chapter_outlines_project_chapter
--     ON chapter_outlines (project_id, chapter_number);


-- Phase 2: Payment tables (created by GORM AutoMigrate, this is the reference DDL)

CREATE TABLE IF NOT EXISTS payment_orders (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    plan_id         INT NOT NULL,
    idempotency_key VARCHAR(64) NOT NULL,
    amount          BIGINT NOT NULL,
    currency        VARCHAR(3) NOT NULL DEFAULT 'cny',
    status          VARCHAR(20) NOT NULL,
    channel         VARCHAR(20) NOT NULL,
    external_id     VARCHAR(128),
    external_event_id VARCHAR(128),
    paid_at         DATETIME(3),
    refunded_at     DATETIME(3),
    metadata        JSON,
    created_at      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),

    INDEX           idx_payment_orders_user_id (user_id),
    INDEX           idx_payment_orders_plan_id (plan_id),
    INDEX           idx_payment_orders_status (status),
    INDEX           idx_payment_orders_external_id (external_id),
    UNIQUE INDEX    idx_payment_orders_idempotency_key (idempotency_key),
    UNIQUE INDEX    idx_payment_orders_external_event_id (external_event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS subscriptions (
    id                   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id              INT NOT NULL,
    plan_id              INT NOT NULL,
    status               VARCHAR(20),
    current_period_start DATETIME(3),
    current_period_end   DATETIME(3),
    cancelled_at         DATETIME(3),
    external_sub_id      VARCHAR(128),
    created_at           DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at           DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),

    UNIQUE INDEX idx_subscriptions_user_id (user_id),
    INDEX        idx_subscriptions_plan_id (plan_id),
    INDEX        idx_subscriptions_status (status),
    INDEX        idx_subscriptions_external_sub_id (external_sub_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- Table partitioning plan (execute when data volume warrants it)
-- NOTE: These are commented out as they require careful planning around existing data.

-- chapter_versions: RANGE partition by id (every 5M rows)
-- ALTER TABLE chapter_versions PARTITION BY RANGE (id) (
--     PARTITION p0 VALUES LESS THAN (5000000),
--     PARTITION p1 VALUES LESS THAN (10000000),
--     PARTITION p2 VALUES LESS THAN (15000000),
--     PARTITION pmax VALUES LESS THAN MAXVALUE
-- );

-- writing_archives: RANGE partition by created_at (time-based, old data archivable)
-- ALTER TABLE writing_archives PARTITION BY RANGE (UNIX_TIMESTAMP(created_at)) (
--     PARTITION p2025 VALUES LESS THAN (UNIX_TIMESTAMP('2026-01-01')),
--     PARTITION p2026 VALUES LESS THAN (UNIX_TIMESTAMP('2027-01-01')),
--     PARTITION pmax VALUES LESS THAN MAXVALUE
-- );
