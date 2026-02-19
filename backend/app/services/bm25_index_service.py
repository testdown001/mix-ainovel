# AIMETA P=BM25倒排索引服务_关键词检索|R=中文分词_倒排索引_BM25评分|NR=不含向量检索|E=BM25IndexService|X=internal|A=BM25索引|D=libsql|S=db|RD=./README.ai
"""
BM25 倒排索引服务 (BM25IndexService)

实现经典 BM25 关键词检索：
- 中文 bigram + unigram 分词（不引入 jieba 等重依赖）
- 英文空格分词
- 经典 BM25 公式（k1=1.5, b=0.75）
- 索引持久化到 libsql

遵循奥卡姆剃刀：使用简单的 n-gram 分词，避免引入重型中文分词依赖。
"""
import logging
import math
import re
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core.config import settings

try:
    import libsql_client
except ImportError:
    libsql_client = None

logger = logging.getLogger(__name__)


class BM25IndexService:
    """BM25 倒排索引服务，基于 libsql 持久化。"""

    K1 = 1.5
    B = 0.75

    def __init__(self, client: Any = None) -> None:
        self._client = client
        self._schema_ready = False

    async def ensure_schema(self) -> None:
        """创建 BM25 相关表。"""
        if not self._client or self._schema_ready:
            return

        statements = [
            """
            CREATE TABLE IF NOT EXISTS rag_bm25_index (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                chapter_number INTEGER NOT NULL,
                term TEXT NOT NULL,
                tf REAL NOT NULL,
                created_at INTEGER DEFAULT (unixepoch())
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_bm25_project_term
            ON rag_bm25_index(project_id, term)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_bm25_chunk_id
            ON rag_bm25_index(chunk_id)
            """,
            """
            CREATE TABLE IF NOT EXISTS rag_bm25_doc_stats (
                project_id TEXT PRIMARY KEY,
                total_docs INTEGER DEFAULT 0,
                avg_doc_len REAL DEFAULT 0,
                updated_at INTEGER DEFAULT (unixepoch())
            )
            """,
        ]

        try:
            for sql in statements:
                await self._client.execute(sql)
            self._schema_ready = True
            logger.info("BM25 索引表结构已就绪。")
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
        if not self._client:
            return
        await self.ensure_schema()

        terms = self.tokenize(content)
        if not terms:
            return

        term_freq: Dict[str, int] = {}
        for term in terms:
            term_freq[term] = term_freq.get(term, 0) + 1

        doc_len = len(terms)

        # 先删除旧索引
        try:
            await self._client.execute(
                "DELETE FROM rag_bm25_index WHERE chunk_id = :chunk_id",
                {"chunk_id": chunk_id},
            )
        except Exception:
            pass

        # 写入新索引
        for term, count in term_freq.items():
            tf = count / doc_len
            try:
                await self._client.execute(
                    """
                    INSERT INTO rag_bm25_index (id, project_id, chunk_id, chapter_number, term, tf)
                    VALUES (:id, :project_id, :chunk_id, :chapter_number, :term, :tf)
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "project_id": project_id,
                        "chunk_id": chunk_id,
                        "chapter_number": chapter_number,
                        "term": term,
                        "tf": tf,
                    },
                )
            except Exception as exc:
                logger.debug("写入 BM25 索引失败: term=%s error=%s", term, exc)

        # 更新文档统计
        await self._update_doc_stats(project_id)

    async def delete_by_chunks(self, chunk_ids: Sequence[str]) -> None:
        """删除指定 chunk 的 BM25 索引。"""
        if not self._client or not chunk_ids:
            return
        await self.ensure_schema()
        for chunk_id in chunk_ids:
            try:
                await self._client.execute(
                    "DELETE FROM rag_bm25_index WHERE chunk_id = :chunk_id",
                    {"chunk_id": chunk_id},
                )
            except Exception as exc:
                logger.debug("删除 BM25 索引失败: chunk_id=%s error=%s", chunk_id, exc)

    async def delete_by_chapters(self, project_id: str, chapter_numbers: Sequence[int]) -> None:
        """按章节号删除 BM25 索引。"""
        if not self._client or not chapter_numbers:
            return
        await self.ensure_schema()
        for ch_num in chapter_numbers:
            try:
                await self._client.execute(
                    "DELETE FROM rag_bm25_index WHERE project_id = :pid AND chapter_number = :ch",
                    {"pid": project_id, "ch": ch_num},
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
        if not self._client:
            return []
        await self.ensure_schema()

        query_terms = self.tokenize(query)
        if not query_terms:
            return []

        # 获取文档统计
        stats = await self._get_doc_stats(project_id)
        total_docs = stats.get("total_docs", 1)
        avg_doc_len = stats.get("avg_doc_len", 100.0)

        # 查询包含查询词的文档
        chunk_scores: Dict[str, float] = {}
        unique_terms = set(query_terms)

        for term in unique_terms:
            try:
                result = await self._client.execute(
                    """
                    SELECT chunk_id, tf FROM rag_bm25_index
                    WHERE project_id = :project_id AND term = :term
                    """,
                    {"project_id": project_id, "term": term},
                )
                rows = self._iter_rows(result)
                df = len(rows)
                if df == 0:
                    continue

                # IDF
                idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)

                for row in rows:
                    chunk_id = row.get("chunk_id", "")
                    tf = float(row.get("tf", 0))
                    # BM25 score component
                    # 简化：假设每个文档长度约等于平均长度
                    tf_norm = (tf * (self.K1 + 1)) / (tf + self.K1 * (1 - self.B + self.B * 1.0))
                    score = idf * tf_norm
                    chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + score

            except Exception as exc:
                logger.debug("BM25 查询失败: term=%s error=%s", term, exc)

        # 排序并返回 top_k
        sorted_results = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [{"chunk_id": cid, "bm25_score": score} for cid, score in sorted_results]

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """中文 bigram+unigram + 英文空格分词。"""
        if not text:
            return []

        tokens: List[str] = []

        # 提取中文字符段和英文单词段
        segments = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)

        for segment in segments:
            if re.match(r'[\u4e00-\u9fff]', segment[0]):
                # 中文：unigram + bigram
                for char in segment:
                    tokens.append(char)
                for i in range(len(segment) - 1):
                    tokens.append(segment[i:i + 2])
            else:
                # 英文：转小写作为一个 token
                tokens.append(segment.lower())

        return tokens

    async def _update_doc_stats(self, project_id: str) -> None:
        """更新项目的文档统计信息。"""
        if not self._client:
            return
        try:
            result = await self._client.execute(
                """
                SELECT COUNT(DISTINCT chunk_id) as total_docs
                FROM rag_bm25_index WHERE project_id = :pid
                """,
                {"pid": project_id},
            )
            rows = self._iter_rows(result)
            total_docs = rows[0].get("total_docs", 0) if rows else 0

            result2 = await self._client.execute(
                """
                SELECT chunk_id, COUNT(*) as term_count
                FROM rag_bm25_index WHERE project_id = :pid
                GROUP BY chunk_id
                """,
                {"pid": project_id},
            )
            rows2 = self._iter_rows(result2)
            avg_len = sum(r.get("term_count", 0) for r in rows2) / max(len(rows2), 1)

            await self._client.execute(
                """
                INSERT INTO rag_bm25_doc_stats (project_id, total_docs, avg_doc_len, updated_at)
                VALUES (:pid, :total, :avg, unixepoch())
                ON CONFLICT(project_id) DO UPDATE SET
                    total_docs=excluded.total_docs,
                    avg_doc_len=excluded.avg_doc_len,
                    updated_at=excluded.updated_at
                """,
                {"pid": project_id, "total": total_docs, "avg": avg_len},
            )
        except Exception as exc:
            logger.debug("更新 BM25 文档统计失败: %s", exc)

    async def _get_doc_stats(self, project_id: str) -> Dict[str, Any]:
        """获取项目的文档统计。"""
        if not self._client:
            return {"total_docs": 1, "avg_doc_len": 100.0}
        try:
            result = await self._client.execute(
                "SELECT total_docs, avg_doc_len FROM rag_bm25_doc_stats WHERE project_id = :pid",
                {"pid": project_id},
            )
            rows = self._iter_rows(result)
            if rows:
                return {
                    "total_docs": max(rows[0].get("total_docs", 1), 1),
                    "avg_doc_len": max(rows[0].get("avg_doc_len", 100.0), 1.0),
                }
        except Exception:
            pass
        return {"total_docs": 1, "avg_doc_len": 100.0}

    @staticmethod
    def _iter_rows(result: Any) -> List[Dict[str, Any]]:
        """统一处理 libsql 返回的行数据。"""
        rows = getattr(result, "rows", None)
        if rows is None:
            rows = result
        if not rows:
            return []
        normalized: List[Dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                normalized.append(row)
            elif hasattr(row, "_asdict"):
                normalized.append(row._asdict())
            else:
                try:
                    normalized.append(dict(row))
                except Exception:
                    continue
        return normalized
