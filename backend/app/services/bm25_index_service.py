# AIMETA P=BM25倒排索引服务_关键词检索|R=中文分词_倒排索引_BM25评分|NR=不含向量检索|E=BM25IndexService|X=internal|A=BM25索引|D=mysql|S=db|RD=./README.ai
"""
BM25 倒排索引服务 (BM25IndexService)

实现经典 BM25 关键词检索：
- 中文 bigram + unigram 分词
- 英文空格分词
- 经典 BM25 公式（k1=1.5, b=0.75）
- 索引持久化到 MySQL 数据库（原为 libsql，现通过 SQLAlchemy 初始化）
"""
import logging
import math
import re
import uuid
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text

from ..core.config import settings
from ..db.session import engine

logger = logging.getLogger(__name__)


class BM25IndexService:
    """BM25 倒排索引服务，基于 MySQL/SQLAlchemy 持久化。"""

    K1 = 1.5
    B = 0.75

    def __init__(self, client: Any = None) -> None:
        # client 参数保留为兼容旧代码，但直接使用从 session 导入的异步 engine
        self._engine = engine
        self._schema_ready = False

    async def ensure_schema(self) -> None:
        """创建 BM25 相关表。"""
        if self._schema_ready:
            return

        statements = [
            """
            CREATE TABLE IF NOT EXISTS rag_bm25_index (
                id VARCHAR(36) PRIMARY KEY,
                project_id VARCHAR(64) NOT NULL,
                chunk_id VARCHAR(64) NOT NULL,
                chapter_number INT NOT NULL,
                term VARCHAR(128) NOT NULL,
                `tf` FLOAT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_bm25_project_term (project_id, term),
                INDEX idx_bm25_chunk_id (chunk_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
            """
            CREATE TABLE IF NOT EXISTS rag_bm25_doc_stats (
                project_id VARCHAR(64) PRIMARY KEY,
                total_docs INT DEFAULT 0,
                avg_doc_len FLOAT DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """,
        ]

        try:
            async with self._engine.begin() as conn:
                for sql in statements:
                    await conn.execute(text(sql))
            self._schema_ready = True
            logger.info("BM25 索引表结构已就绪 (MySQL)。")
        except Exception as exc:
            logger.error("创建 BM25 表结构失败: %s", exc)

    async def index_chunk(
        self,
        *,
        project_id: str,
        chunk_id: str,
        chapter_number: int,
        content: str,
    ) -> None:
        """为单个 chunk 构建 BM25 倒排索引。"""
        await self.ensure_schema()

        terms = self.tokenize(content)
        if not terms:
            return

        term_freq: Dict[str, int] = {}
        for term in terms:
            term_freq[term] = term_freq.get(term, 0) + 1

        doc_len = len(terms)

        async with self._engine.begin() as conn:
            # 先删除旧索引
            await conn.execute(
                text("DELETE FROM rag_bm25_index WHERE chunk_id = :chunk_id"),
                {"chunk_id": chunk_id}
            )

            # 写入新索引
            for term, count in term_freq.items():
                tf = count / doc_len
                # truncate term to avoid index limits if needed
                term_val = term[:128]
                try:
                    await conn.execute(
                        text("""
                        INSERT INTO rag_bm25_index (id, project_id, chunk_id, chapter_number, term, `tf`)
                        VALUES (:id, :project_id, :chunk_id, :chapter_number, :term, :tf)
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "project_id": project_id,
                            "chunk_id": chunk_id,
                            "chapter_number": chapter_number,
                            "term": term_val,
                            "tf": tf,
                        }
                    )
                except Exception as exc:
                    logger.debug("写入 BM25 索引失败: term=%s error=%s", term_val, exc)

        # 更新文档统计
        await self._update_doc_stats(project_id)

    async def delete_by_chunks(self, chunk_ids: Sequence[str]) -> None:
        """删除指定 chunk 的 BM25 索引。"""
        if not chunk_ids:
            return
        await self.ensure_schema()
        async with self._engine.begin() as conn:
            for chunk_id in chunk_ids:
                try:
                    await conn.execute(
                        text("DELETE FROM rag_bm25_index WHERE chunk_id = :chunk_id"),
                        {"chunk_id": chunk_id}
                    )
                except Exception as exc:
                    logger.debug("删除 BM25 索引失败: chunk_id=%s error=%s", chunk_id, exc)

    async def delete_by_chapters(self, project_id: str, chapter_numbers: Sequence[int]) -> None:
        """按章节号删除 BM25 索引。"""
        if not chapter_numbers:
            return
        await self.ensure_schema()
        async with self._engine.begin() as conn:
            for ch_num in chapter_numbers:
                try:
                    await conn.execute(
                        text("DELETE FROM rag_bm25_index WHERE project_id = :pid AND chapter_number = :ch"),
                        {"pid": project_id, "ch": ch_num}
                    )
                except Exception as exc:
                    logger.debug("删除 BM25 索引失败: chapter=%d error=%s", ch_num, exc)
        await self._update_doc_stats(project_id)

    async def search(
        self,
        *,
        project_id: str,
        query: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """BM25 关键词检索，返回按相关度排序的 chunk_id 和分数。"""
        await self.ensure_schema()

        query_terms = self.tokenize(query)
        if not query_terms:
            return []

        # 获取文档统计
        stats = await self._get_doc_stats(project_id)
        total_docs = stats.get("total_docs", 1)
        avg_doc_len = stats.get("avg_doc_len", 100.0)

        chunk_scores: Dict[str, float] = {}
        unique_terms = set(query_terms)

        async with self._engine.begin() as conn:
            for term in unique_terms:
                try:
                    term_val = term[:128]
                    result = await conn.execute(
                        text("""
                        SELECT chunk_id, `tf` FROM rag_bm25_index
                        WHERE project_id = :project_id AND term = :term
                        """),
                        {"project_id": project_id, "term": term_val}
                    )
                    rows = result.mappings().fetchall()
                    df = len(rows)
                    if df == 0:
                        continue

                    # IDF
                    idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)

                    for row in rows:
                        chunk_id = row["chunk_id"]
                        tf = float(row["tf"])
                        tf_norm = (tf * (self.K1 + 1)) / (tf + self.K1 * (1 - self.B + self.B * 1.0))
                        score = idf * tf_norm
                        chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + score

                except Exception as exc:
                    logger.debug("BM25 查询失败: term=%s error=%s", term, exc)

        sorted_results = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [{"chunk_id": cid, "bm25_score": score} for cid, score in sorted_results]

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """中文 bigram+unigram + 英文空格分词。"""
        if not text:
            return []
        
        tokens: List[str] = []
        segments = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)

        for segment in segments:
            if re.match(r'[\u4e00-\u9fff]', segment[0]):
                for char in segment:
                    tokens.append(char)
                for i in range(len(segment) - 1):
                    tokens.append(segment[i:i + 2])
            else:
                tokens.append(segment.lower())

        return tokens

    async def _update_doc_stats(self, project_id: str) -> None:
        """更新项目的文档统计信息。"""
        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(
                    text("""
                    SELECT COUNT(DISTINCT chunk_id) as total_docs
                    FROM rag_bm25_index WHERE project_id = :pid
                    """),
                    {"pid": project_id}
                )
                total_docs = result.scalar() or 0

                result2 = await conn.execute(
                    text("""
                    SELECT chunk_id, COUNT(*) as term_count
                    FROM rag_bm25_index WHERE project_id = :pid
                    GROUP BY chunk_id
                    """),
                    {"pid": project_id}
                )
                rows2 = result2.mappings().fetchall()
                avg_len = sum(r["term_count"] for r in rows2) / max(len(rows2), 1)

                await conn.execute(
                    text("""
                    INSERT INTO rag_bm25_doc_stats (project_id, total_docs, avg_doc_len)
                    VALUES (:pid, :total, :avg)
                    ON DUPLICATE KEY UPDATE
                        total_docs=VALUES(total_docs),
                        avg_doc_len=VALUES(avg_doc_len)
                    """),
                    {"pid": project_id, "total": total_docs, "avg": avg_len}
                )
        except Exception as exc:
            logger.debug("更新 BM25 文档统计失败: %s", exc)

    async def _get_doc_stats(self, project_id: str) -> Dict[str, Any]:
        """获取项目的文档统计。"""
        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(
                    text("SELECT total_docs, avg_doc_len FROM rag_bm25_doc_stats WHERE project_id = :pid"),
                    {"pid": project_id}
                )
                row = result.mappings().first()
                if row:
                    return {
                        "total_docs": max(row["total_docs"], 1),
                        "avg_doc_len": max(row["avg_doc_len"], 1.0),
                    }
        except Exception:
            pass
        return {"total_docs": 1, "avg_doc_len": 100.0}
