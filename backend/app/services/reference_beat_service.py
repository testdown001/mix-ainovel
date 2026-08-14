# AIMETA P=参考桥段选取_按本章情境检索注入|R=select_beats_for_chapter_格式化|NR=不含抽取|E=ReferenceBeatService|X=internal|A=服务类|D=llm|S=compute|RD=./README.ai
"""参考桥段的按情境选取与格式化。

桥段库（ReferenceNovel.beat_library）是「情境 → 手法」条目：什么局面、怎么铺、
靠什么转、情绪在哪兑现。本模块回答「写这一章该看哪几条」：

- 规模是 3 本 × 8-15 条 ≈ 最多 45 条，不建 Qdrant collection——一次 batch embedding
  + 内存余弦排序足够；情境向量按 (novel_id, updated_at) 进程内缓存，换书或重分析自动失效。
- 嵌入不可用时（get_embeddings_batch 失败返回空）回退标签/字符重叠打分，
  两条路径都必须给出结果——降级可以变糙，不能变没有。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from ..utils.vector_math import cosine_similarity

logger = logging.getLogger(__name__)

# 情境向量缓存：key = f"{novel_id}:{updated_at}"，value = {beat_index: embedding}
_SITUATION_EMBEDDING_CACHE: Dict[str, List[List[float]]] = {}
_CACHE_MAX_ENTRIES = 64


def _collect_beats(novels: Sequence[Any]) -> List[Dict[str, Any]]:
    """把各参考小说的桥段拍平成带出处的列表；缺 beat_library 的老数据自然为空。"""
    collected: List[Dict[str, Any]] = []
    for novel in novels or []:
        library = getattr(novel, "beat_library", None)
        if not isinstance(library, dict):
            continue
        for beat in library.get("beats") or []:
            if not isinstance(beat, dict):
                continue
            situation = str(beat.get("situation") or "").strip()
            if not situation:
                continue
            collected.append({**beat, "source_novel": novel.title})
    return collected


def _keyword_score(beat: Dict[str, Any], query_text: str) -> float:
    """无嵌入时的回退打分：标签命中为主，情境字符 bigram 重叠为辅。"""
    score = 0.0
    for tag in beat.get("tags") or []:
        tag_text = str(tag).strip()
        if tag_text and tag_text in query_text:
            score += 1.0
    situation = str(beat.get("situation") or "")
    bigrams = {situation[i : i + 2] for i in range(len(situation) - 1)}
    query_bigrams = {query_text[i : i + 2] for i in range(len(query_text) - 1)}
    if bigrams and query_bigrams:
        score += len(bigrams & query_bigrams) / len(bigrams)
    return score


class ReferenceBeatService:
    def __init__(self, llm_service):
        self.llm_service = llm_service

    async def select_beats_for_chapter(
        self,
        novels: Sequence[Any],
        *,
        query_text: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """按本章情境（大纲摘要 + 使命要点拼成的 query）选出最相关的桥段。"""
        beats = _collect_beats(novels)
        if not beats or not (query_text or "").strip():
            return []
        if len(beats) <= top_k:
            return beats

        scores = await self._semantic_scores(novels, beats, query_text)
        if scores is None:
            scores = [_keyword_score(beat, query_text) for beat in beats]

        ranked = sorted(range(len(beats)), key=lambda i: scores[i], reverse=True)
        return [beats[i] for i in ranked[:top_k]]

    async def _semantic_scores(
        self,
        novels: Sequence[Any],
        beats: List[Dict[str, Any]],
        query_text: str,
    ) -> Optional[List[float]]:
        """嵌入打分；任何一步失败返回 None 交给关键词回退。"""
        try:
            situation_vectors = await self._situation_embeddings(novels, beats)
            if situation_vectors is None:
                return None
            query_vectors = await self.llm_service.get_embeddings_batch([query_text[:512]])
            if not query_vectors or not query_vectors[0]:
                return None
            query_vector = query_vectors[0]
            return [
                cosine_similarity(query_vector, vector) if vector else 0.0
                for vector in situation_vectors
            ]
        except Exception as exc:  # noqa: BLE001 - 打分失败必须降级而不是让生成失败
            logger.warning("参考桥段语义打分失败，回退关键词匹配: %s", exc)
            return None

    async def _situation_embeddings(
        self,
        novels: Sequence[Any],
        beats: List[Dict[str, Any]],
    ) -> Optional[List[List[float]]]:
        """全部桥段的情境向量（与 beats 顺序一致）；按书缓存，任何书失败即整体放弃。"""
        per_novel: Dict[str, List[List[float]]] = {}
        for novel in novels or []:
            library = getattr(novel, "beat_library", None)
            if not isinstance(library, dict):
                continue
            situations = [
                str(beat.get("situation") or "").strip()
                for beat in library.get("beats") or []
                if isinstance(beat, dict) and str(beat.get("situation") or "").strip()
            ]
            if not situations:
                continue
            cache_key = f"{getattr(novel, 'id', '?')}:{getattr(novel, 'updated_at', '')}"
            cached = _SITUATION_EMBEDDING_CACHE.get(cache_key)
            if cached is None or len(cached) != len(situations):
                vectors = await self.llm_service.get_embeddings_batch(situations)
                if not vectors or any(not vector for vector in vectors):
                    return None
                if len(_SITUATION_EMBEDDING_CACHE) >= _CACHE_MAX_ENTRIES:
                    _SITUATION_EMBEDDING_CACHE.clear()
                _SITUATION_EMBEDDING_CACHE[cache_key] = vectors
                cached = vectors
            per_novel[novel.title] = cached

        ordered: List[List[float]] = []
        cursor: Dict[str, int] = {}
        for beat in beats:
            title = beat["source_novel"]
            vectors = per_novel.get(title)
            index = cursor.get(title, 0)
            if vectors is None or index >= len(vectors):
                return None
            ordered.append(vectors[index])
            cursor[title] = index + 1
        return ordered

    # ------------------------------------------------------------------
    # 格式化
    # ------------------------------------------------------------------

    @staticmethod
    def format_beats_for_prompt(beats: List[Dict[str, Any]]) -> str:
        """正文生成用：完整手法（铺垫/转折/兑现/翻车点），供作者迁移思路。"""
        if not beats:
            return ""
        parts: List[str] = [
            "以下桥段来自参考小说在相似局面下的处理手法，供迁移思路使用；"
            "禁止照搬情节与专有设定，重点参考其铺垫方式、转折触发与情绪兑现点。"
        ]
        for beat in beats:
            lines = [f"◆ {beat.get('name') or '未命名桥段'}（出自《{beat.get('source_novel', '?')}》）"]
            if beat.get("situation"):
                lines.append(f"  适用局面：{beat['situation']}")
            if beat.get("setup"):
                lines.append(f"  铺垫：{beat['setup']}")
            if beat.get("turn"):
                lines.append(f"  转折：{beat['turn']}")
            if beat.get("payoff"):
                lines.append(f"  兑现：{beat['payoff']}")
            if beat.get("pitfalls"):
                lines.append(f"  勿踩：{beat['pitfalls']}")
            parts.append("\n".join(lines))
        return "\n\n".join(parts)

    @staticmethod
    def format_beat_index_for_concept(novels: Sequence[Any], *, max_beats: int = 12) -> str:
        """灵感对话用：压缩索引（名字+情境+标签），让 AI 构思时能点名引用具体手法。"""
        beats = _collect_beats(novels)
        if not beats:
            return ""
        lines: List[str] = []
        for beat in beats[:max_beats]:
            tags = "/".join(str(t) for t in (beat.get("tags") or [])[:4])
            suffix = f"（{tags}）" if tags else ""
            lines.append(
                f"- {beat.get('name') or '未命名'}【《{beat.get('source_novel', '?')}》】：{beat.get('situation', '')}{suffix}"
            )
        return "\n".join(lines)

    @staticmethod
    def format_structure_for_blueprint(novels: Sequence[Any]) -> str:
        """蓝图章纲用：全书级结构手法（分卷节奏/冲突升级/钩子形态）。"""
        sections: List[str] = []
        for novel in novels or []:
            library = getattr(novel, "beat_library", None)
            if not isinstance(library, dict):
                continue
            structure = library.get("structure") or {}
            if not isinstance(structure, dict):
                continue
            lines: List[str] = []
            if structure.get("volume_rhythm"):
                lines.append(f"  分卷节奏：{structure['volume_rhythm']}")
            if structure.get("conflict_escalation"):
                lines.append(f"  冲突升级：{structure['conflict_escalation']}")
            if structure.get("hook_pattern"):
                lines.append(f"  章末钩子：{structure['hook_pattern']}")
            if lines:
                sections.append(f"《{novel.title}》的结构手法：\n" + "\n".join(lines))
        return "\n\n".join(sections)
