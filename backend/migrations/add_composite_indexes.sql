-- 性能优化：添加复合索引
-- 创建时间: 2026-03-13
-- 目的: 优化常见查询模式，减少查询时间

-- 1. chapter_outlines 表：优化 (project_id, chapter_number) 查询
-- 使用场景: 获取特定项目的特定章节大纲
ALTER TABLE chapter_outlines
ADD INDEX idx_project_chapter (project_id, chapter_number);

-- 2. chapters 表：优化 (project_id, chapter_number) 查询
-- 使用场景: 获取特定项目的特定章节
ALTER TABLE chapters
ADD INDEX idx_project_chapter (project_id, chapter_number);

-- 3. chapter_blueprints 表：优化 (project_id, chapter_number) 查询
-- 使用场景: 获取特定项目的特定章节蓝图
ALTER TABLE chapter_blueprints
ADD INDEX idx_project_chapter (project_id, chapter_number);

-- 4. foreshadowings 表：优化 (project_id, importance) 查询
-- 使用场景: 按重要性获取项目的伏笔
ALTER TABLE foreshadowings
ADD INDEX idx_project_importance (project_id, importance);

-- 5. foreshadowings 表：优化 (project_id, status) 查询
-- 使用场景: 按状态获取项目的伏笔
ALTER TABLE foreshadowings
ADD INDEX idx_project_status (project_id, status);

-- 6. blueprint_characters 表：优化 (project_id, position) 查询
-- 使用场景: 按位置排序获取角色列表
ALTER TABLE blueprint_characters
ADD INDEX idx_project_position (project_id, position);

-- 7. chapter_versions 表：优化 (chapter_id, created_at) 查询
-- 使用场景: 按时间排序获取章节版本
ALTER TABLE chapter_versions
ADD INDEX idx_chapter_created (chapter_id, created_at);

-- 8. novel_conversations 表：优化 (project_id, seq) 查询
-- 使用场景: 按顺序获取对话记录
ALTER TABLE novel_conversations
ADD INDEX idx_project_seq (project_id, seq);
