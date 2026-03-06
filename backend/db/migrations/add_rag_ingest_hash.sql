-- 为 chapters 表添加 rag_ingest_hash 字段，用于 RAG 增量索引
-- 记录每章入库时的内容哈希，刷新知识库时跳过未变更的章节

ALTER TABLE chapters ADD COLUMN rag_ingest_hash VARCHAR(64) DEFAULT NULL;
