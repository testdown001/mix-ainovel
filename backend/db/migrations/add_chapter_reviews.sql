-- 迁移脚本：添加 chapter_reviews 表（门下省审核机制）
-- 创建时间: 2026-03-07
-- 功能: 存储章节质量审核结果

-- 创建 chapter_reviews 表
CREATE TABLE IF NOT EXISTS chapter_reviews (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '审核记录ID',
    project_id VARCHAR(36) NOT NULL COMMENT '项目ID',
    chapter_number INT NOT NULL COMMENT '章节号',

    -- 审核结果
    approved TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否通过审核',
    overall_score FLOAT NOT NULL COMMENT '综合评分',

    -- 各维度评分 (JSON)
    scores JSON COMMENT '{"consistency": 85, "character_depth": 70, "pacing": 90, "foreshadowing": 60, "prose_quality": 75, "emotion_curve": 80}',

    -- 问题列表 (JSON)
    issues JSON COMMENT '[{"type": "foreshadowing", "severity": "high", "description": "...", "suggestion": "..."}]',

    -- 审核意见
    review_comment TEXT COMMENT '总体评价',

    -- 是否需要重写
    rewrite_required TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否需要重写',

    -- 关联章节版本
    chapter_version_id BIGINT COMMENT '章节版本ID',

    -- 创建时间
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',

    -- 索引
    INDEX idx_project_chapter (project_id, chapter_number),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT '章节审核记录';
