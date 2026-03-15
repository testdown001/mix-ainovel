from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from ..core.constants import CHAPTER_MAX_WORDS, CHAPTER_MIN_WORDS


_PLACEHOLDER_MARKERS = (
    "TODO",
    "TBD",
    "待补",
    "待续",
    "（略）",
    "[待补]",
    "[TODO]",
)

_SCORE_KEYS = ("overall_score", "final_score", "avg_score", "score")


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _normalize_count(value: Any) -> tuple[int, int]:
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        return len(items), sum(1 for item in items if item)
    if isinstance(value, (int, float)):
        count = max(0, int(value))
        return count, count
    return 0, 0


def extract_retrieval_metrics(retrieval_stats: Any) -> Dict[str, float | int]:
    if not isinstance(retrieval_stats, dict):
        return {"chunks": 0, "summaries": 0, "hit_rate": 0.0}

    chunk_count, chunk_non_empty = _normalize_count(retrieval_stats.get("chunks", []))
    summary_count, summary_non_empty = _normalize_count(retrieval_stats.get("summaries", []))
    total_items = chunk_count + summary_count
    total_non_empty = chunk_non_empty + summary_non_empty

    explicit_hit_rate = _coerce_float(
        retrieval_stats.get("hit_rate", retrieval_stats.get("rag_hit_rate"))
    )
    if explicit_hit_rate is not None:
        if explicit_hit_rate > 1:
            explicit_hit_rate = explicit_hit_rate / 100
        hit_rate = max(0.0, min(1.0, explicit_hit_rate))
    elif total_items > 0:
        hit_rate = total_non_empty / total_items
    else:
        hit_rate = 0.0

    return {
        "chunks": chunk_count,
        "summaries": summary_count,
        "hit_rate": round(hit_rate, 4),
    }


def extract_review_scores(review_summaries: Any) -> List[Tuple[str, float]]:
    collected: List[Tuple[str, float]] = []
    seen: set[Tuple[str, float]] = set()

    def _walk(node: Any, label: str) -> None:
        if isinstance(node, dict):
            node_label = label or "review"
            for score_key in _SCORE_KEYS:
                if score_key not in node:
                    continue
                score = _coerce_float(node.get(score_key))
                if score is None or score < 0 or score > 100:
                    continue
                item = (node_label, round(score, 2))
                if item not in seen:
                    seen.add(item)
                    collected.append(item)
                break

            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    _walk(value, key.replace("_", " "))

        elif isinstance(node, list):
            for value in node:
                if isinstance(value, (dict, list)):
                    _walk(value, label)

    _walk(review_summaries, "")
    return collected


def extract_review_issues(review_summaries: Any) -> List[Dict[str, str]]:
    if not isinstance(review_summaries, dict):
        return []

    issues: List[Dict[str, str]] = []
    seen: set[Tuple[str, str]] = set()

    for name, payload in review_summaries.items():
        if not isinstance(payload, dict):
            continue

        label = name.replace("_", " ")
        error_message = payload.get("error")
        if error_message:
            item = (
                label,
                str(error_message),
            )
            if item not in seen:
                seen.add(item)
                issues.append(
                    {
                        "type": f"{label}分析",
                        "severity": "warning",
                        "description": f"{label}分析未完成：{str(error_message)[:120]}",
                    }
                )
            continue

        status = payload.get("status")
        if status in {"scheduled", "scheduled_async"}:
            item = (label, str(status))
            if item not in seen:
                seen.add(item)
                issues.append(
                    {
                        "type": f"{label}分析",
                        "severity": "info",
                        "description": f"{label}分析仍在后台执行，当前结果可能尚未完全入库",
                    }
                )

    return issues


def analyze_chapter_text(content: str) -> Dict[str, Any]:
    text = (content or "").strip()
    if not text:
        return {
            "metrics": {
                "word_count": 0,
                "paragraph_count": 0,
                "longest_paragraph_chars": 0,
                "avg_paragraph_chars": 0,
                "dialogue_ratio": 0.0,
                "placeholder_count": 0,
            },
            "issues": [
                {
                    "type": "章节内容",
                    "severity": "error",
                    "description": "当前章节正文为空，无法进行正文质量诊断",
                }
            ],
            "suggestions": ["请先生成或保存章节正文，再重新执行诊断"],
        }

    compact_text = re.sub(r"\s+", "", text)
    word_count = len(compact_text)

    paragraphs = [segment.strip() for segment in re.split(r"\n\s*\n+", text) if segment.strip()]
    if len(paragraphs) <= 1:
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]

    paragraph_lengths = [len(re.sub(r"\s+", "", paragraph)) for paragraph in paragraphs]
    longest_paragraph = max(paragraph_lengths, default=0)
    avg_paragraph = int(sum(paragraph_lengths) / len(paragraph_lengths)) if paragraph_lengths else 0

    dialogue_matches = re.findall(r"[“\"「『](.*?)[”\"」』]", text, flags=re.S)
    dialogue_chars = sum(len(re.sub(r"\s+", "", item)) for item in dialogue_matches)
    dialogue_ratio = round(dialogue_chars / word_count, 4) if word_count else 0.0

    placeholder_hits = sum(1 for marker in _PLACEHOLDER_MARKERS if marker in text)

    issues: List[Dict[str, str]] = []
    suggestions: List[str] = []

    if word_count < CHAPTER_MIN_WORDS * 0.6:
        issues.append(
            {
                "type": "章节字数",
                "severity": "error",
                "description": f"正文约 {word_count} 字，明显低于建议下限 {CHAPTER_MIN_WORDS} 字，剧情展开可能不充分",
            }
        )
        suggestions.append("建议补足关键场景、冲突推进和收尾钩子，使章节体量接近目标字数")
    elif word_count < CHAPTER_MIN_WORDS:
        issues.append(
            {
                "type": "章节字数",
                "severity": "warning",
                "description": f"正文约 {word_count} 字，低于建议下限 {CHAPTER_MIN_WORDS} 字，可适当补强场景层次",
            }
        )
    elif word_count > CHAPTER_MAX_WORDS * 1.1:
        issues.append(
            {
                "type": "章节字数",
                "severity": "error",
                "description": f"正文约 {word_count} 字，明显超过建议上限 {CHAPTER_MAX_WORDS} 字，可能影响节奏和稳定性",
            }
        )
        suggestions.append("建议压缩重复描写和无效过渡，把篇幅让给关键冲突与信息揭示")
    elif word_count > CHAPTER_MAX_WORDS:
        issues.append(
            {
                "type": "章节字数",
                "severity": "warning",
                "description": f"正文约 {word_count} 字，超过建议上限 {CHAPTER_MAX_WORDS} 字，可考虑进一步精简",
            }
        )

    if longest_paragraph >= 220:
        issues.append(
            {
                "type": "段落长度",
                "severity": "warning",
                "description": f"最长段落约 {longest_paragraph} 字，连续大段文字会削弱阅读节奏",
            }
        )
        suggestions.append("建议把大段叙述拆成更短的动作、对白和心理片段，提升可读性")
    elif word_count >= 1500 and len(paragraphs) <= 3:
        issues.append(
            {
                "type": "分段密度",
                "severity": "info",
                "description": f"全文仅识别到 {len(paragraphs)} 个段落，建议增加段落切分以改善节奏",
            }
        )

    if word_count >= 1200 and dialogue_ratio < 0.08:
        issues.append(
            {
                "type": "对话密度",
                "severity": "info",
                "description": f"对话占比约 {dialogue_ratio * 100:.1f}%，若本章并非纯抒情/纯动作章，可适当增加角色交互",
            }
        )

    if "<think>" in text or "</think>" in text:
        issues.append(
            {
                "type": "输出清洗",
                "severity": "warning",
                "description": "正文中仍包含 think 标记，说明生成结果可能未完全清洗",
            }
        )
        suggestions.append("建议重新保存章节或走一次正文清洗流程，移除 think 标签后再继续使用")

    if placeholder_hits:
        issues.append(
            {
                "type": "占位符残留",
                "severity": "warning",
                "description": f"正文中发现 {placeholder_hits} 处疑似占位符/草稿标记，建议人工检查",
            }
        )
        suggestions.append("请检查正文中是否遗留 TODO、待补、待续 等草稿标记")

    return {
        "metrics": {
            "word_count": word_count,
            "paragraph_count": len(paragraphs),
            "longest_paragraph_chars": longest_paragraph,
            "avg_paragraph_chars": avg_paragraph,
            "dialogue_ratio": dialogue_ratio,
            "placeholder_count": placeholder_hits,
        },
        "issues": issues,
        "suggestions": suggestions,
    }
