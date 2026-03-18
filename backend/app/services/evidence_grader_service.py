# AIMETA P=证据相关性评分服务|R=轻量级LLM评分_过滤低质量证据|NR=不含检索逻辑|E=EvidenceGraderService|X=internal|A=证据评分|D=asyncio|S=llm|RD=./README.ai
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .context_planner_service import ContextPlan, EvidenceItem, GenerationEvidencePack

logger = logging.getLogger(__name__)

GRADER_SYSTEM_PROMPT = """你是证据相关性评审员。给定写作目标和一组检索到的证据片段，对每个片段评估其与当前章节写作目标的相关性（0.0-1.0），并给出一句话理由。

评分标准：
- 0.8-1.0：与本章核心目标直接相关，必须保留
- 0.5-0.8：间接相关，提供有用背景或约束
- 0.3-0.5：弱相关，可能有轻微参考价值
- 0.0-0.3：不相关，应过滤

请严格返回 JSON 数组，不要输出其他内容：
[{"index": 1, "score": 0.85, "reason": "..."}, ...]"""

MAX_CONTENT_PREVIEW = 200


@dataclass
class GradeResult:
    item_index: int
    relevance_score: float
    reason: str


class EvidenceGraderService:
    """对 EvidenceRouterService 收集的证据做轻量级 LLM 相关性评分。

    设计约束：
    - 使用 llm_grader.* 配置的极速小模型（Haiku / 8B 级别）
    - 未配置时跳过评分，不影响现有流程
    - fast_path 模式下跳过评分
    - 单次批量评分，最多重试一次
    - 评分结果写回 EvidenceItem.metadata，不删除低分证据
    """

    def __init__(self, llm_service):
        self.llm_service = llm_service

    async def grade(
        self,
        *,
        evidence_pack: GenerationEvidencePack,
        plan: ContextPlan,
        threshold: float = 0.3,
        max_retries: int = 1,
    ) -> Dict[str, Any]:
        """对 evidence_pack 中所有 items 做相关性评分。

        Returns:
            {"graded": True, "total": N, "filtered": M, "scores": [...]}
            或 {"graded": False, "reason": "..."}
        """
        if getattr(plan, "is_fast_path", False):
            return {"graded": False, "reason": "fast_path"}

        grader_config = await self._resolve_grader_config()
        if grader_config is None:
            return {"graded": False, "reason": "grader_not_configured"}

        all_items = self._collect_all_items(evidence_pack)
        if not all_items:
            return {"graded": False, "reason": "no_evidence_items"}

        intent = getattr(plan, "intent", {}) or {}
        core_goal = intent.get("core_goal", "") if isinstance(intent, dict) else ""
        chapter_phase = getattr(plan, "chapter_phase", "development")

        grade_results = await self._call_grader(
            items=all_items,
            core_goal=core_goal,
            chapter_phase=chapter_phase,
            config=grader_config,
            max_retries=max_retries,
        )

        if grade_results is None:
            return {"graded": False, "reason": "grader_call_failed"}

        filtered_count = 0
        scores_detail: List[Dict[str, Any]] = []

        for result in grade_results:
            idx = result.item_index
            if idx < 0 or idx >= len(all_items):
                continue
            item = all_items[idx]
            item.metadata["grader_score"] = result.relevance_score
            item.metadata["grader_reason"] = result.reason
            if result.relevance_score < threshold:
                item.metadata["graded_out"] = True
                filtered_count += 1
            scores_detail.append({
                "index": idx,
                "title": item.title,
                "source": item.source,
                "original_score": item.score,
                "grader_score": result.relevance_score,
                "reason": result.reason,
                "graded_out": result.relevance_score < threshold,
            })

        return {
            "graded": True,
            "total": len(all_items),
            "filtered": filtered_count,
            "threshold": threshold,
            "scores": scores_detail,
        }

    async def _resolve_grader_config(self) -> Optional[Dict[str, Optional[str]]]:
        """解析 llm_grader.* 配置，未配置时返回 None。"""
        try:
            return await self.llm_service._resolve_grader_llm_config()
        except Exception:
            return None

    async def _call_grader(
        self,
        *,
        items: List[EvidenceItem],
        core_goal: str,
        chapter_phase: str,
        config: Dict[str, Optional[str]],
        max_retries: int,
    ) -> Optional[List[GradeResult]]:
        """调用轻量级 LLM 对证据做批量评分。"""
        user_content = self._build_grader_prompt(items, core_goal, chapter_phase)

        for attempt in range(1 + max_retries):
            try:
                raw_response = await self.llm_service.get_grader_llm_response(
                    system_prompt=GRADER_SYSTEM_PROMPT,
                    conversation_history=[{"role": "user", "content": user_content}],
                    temperature=0.1,
                    timeout=30.0,
                    max_tokens=2000,
                    config_override=config,
                )
                results = self._parse_grader_response(raw_response, len(items))
                if results is not None:
                    return results
                logger.warning("证据评分 LLM 返回解析失败 (attempt %d)", attempt + 1)
            except Exception as exc:
                logger.warning("证据评分 LLM 调用失败 (attempt %d): %s", attempt + 1, exc)

        return None

    def _build_grader_prompt(
        self,
        items: List[EvidenceItem],
        core_goal: str,
        chapter_phase: str,
    ) -> str:
        parts = [
            f"写作目标：{core_goal or '未指定'}",
            f"章节阶段：{chapter_phase or 'development'}",
            "证据列表：",
        ]
        for idx, item in enumerate(items):
            content_preview = (item.content or "")[:MAX_CONTENT_PREVIEW]
            parts.append(
                json.dumps(
                    {"index": idx, "source": item.source, "title": item.title, "content": content_preview},
                    ensure_ascii=False,
                )
            )
        return "\n".join(parts)

    @staticmethod
    def _parse_grader_response(raw: str, expected_count: int) -> Optional[List[GradeResult]]:
        """从 LLM 响应中解析评分结果。"""
        text = raw.strip()
        # 尝试提取 JSON 数组
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return None

        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

        if not isinstance(data, list):
            return None

        results: List[GradeResult] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            try:
                idx = int(entry.get("index", -1))
                score = float(entry.get("score", 0.0))
                reason = str(entry.get("reason", ""))
                score = max(0.0, min(1.0, score))
                results.append(GradeResult(item_index=idx, relevance_score=score, reason=reason))
            except (TypeError, ValueError):
                continue

        return results if results else None

    @staticmethod
    def _collect_all_items(pack) -> List[EvidenceItem]:
        """收集 evidence_pack 中所有 EvidenceItem。"""
        all_items: List[EvidenceItem] = []
        for attr in ("local_plot", "global_arc", "state_items", "symbolic_items"):
            items = getattr(pack, attr, None)
            if items:
                all_items.extend(items)
        return all_items
