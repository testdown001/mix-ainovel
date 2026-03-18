"""Token 预算执行服务，防止 Prompt 过载和成本激增。"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BudgetEnforcerService:
    """统一的 Token 预算执行器。"""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算文本的 Token 数量（1 token ≈ 1.5 中文字符）。"""
        if not text:
            return 0
        return int(len(text) / 1.5)

    @staticmethod
    def truncate_to_budget(text: str, max_tokens: int) -> tuple[str, bool]:
        """截断文本到指定 Token 预算。

        Args:
            text: 原始文本
            max_tokens: 最大 Token 数

        Returns:
            (截断后的文本, 是否发生了截断)
        """
        if not text:
            return text, False

        estimated_tokens = BudgetEnforcerService.estimate_tokens(text)
        if estimated_tokens <= max_tokens:
            return text, False

        # 截断到预算内（保留 95% 以避免边界问题）
        target_chars = int(max_tokens * 1.5 * 0.95)
        truncated = text[:target_chars]

        # 尝试在句子边界截断
        for delimiter in ["。", "！", "？", "\n", ".", "!", "?"]:
            last_pos = truncated.rfind(delimiter)
            if last_pos > target_chars * 0.8:  # 至少保留 80%
                truncated = truncated[:last_pos + 1]
                break

        logger.warning(
            "文本超出预算被截断: %d tokens -> %d tokens (预算: %d)",
            estimated_tokens,
            BudgetEnforcerService.estimate_tokens(truncated),
            max_tokens,
        )
        return truncated, True

    @staticmethod
    def enforce_retrieval_budget(
        items: List[Dict[str, Any]],
        task_id: str,
        budget: Dict[str, Any],
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """对检索结果执行预算控制。

        Args:
            items: 检索结果列表
            task_id: 任务 ID
            budget: 任务预算配置

        Returns:
            (预算内的结果列表, 预算执行报告)
        """
        max_items = budget.get("max_items", 5)
        max_tokens = budget.get("max_tokens", 2000)
        priority = budget.get("priority", 1)

        # 按优先级排序（如果有 score 字段）
        sorted_items = sorted(
            items,
            key=lambda x: x.get("score", 0.0),
            reverse=True,
        )

        # 限制数量
        limited_items = sorted_items[:max_items]

        # 限制 Token
        result_items = []
        total_tokens = 0
        truncated_count = 0

        for item in limited_items:
            content = str(item.get("content", ""))
            item_tokens = BudgetEnforcerService.estimate_tokens(content)

            # 检查是否超出总预算
            if total_tokens + item_tokens > max_tokens:
                # 尝试截断当前项
                remaining_budget = max_tokens - total_tokens
                if remaining_budget > 100:  # 至少保留 100 tokens
                    truncated_content, was_truncated = BudgetEnforcerService.truncate_to_budget(
                        content, remaining_budget
                    )
                    if was_truncated:
                        truncated_count += 1
                    result_items.append({**item, "content": truncated_content})
                    total_tokens += BudgetEnforcerService.estimate_tokens(truncated_content)
                break
            else:
                result_items.append(item)
                total_tokens += item_tokens

        report = {
            "task_id": task_id,
            "original_count": len(items),
            "result_count": len(result_items),
            "total_tokens": total_tokens,
            "max_tokens": max_tokens,
            "utilization": total_tokens / max_tokens if max_tokens > 0 else 0,
            "truncated_count": truncated_count,
            "dropped_count": len(limited_items) - len(result_items),
            "priority": priority,
        }

        if report["utilization"] >= 0.8:
            logger.info(
                "检索任务 %s 预算使用率: %.1f%% (%d/%d tokens)",
                task_id,
                report["utilization"] * 100,
                total_tokens,
                max_tokens,
            )

        return result_items, report

    @staticmethod
    def enforce_context_budget(
        context_parts: Dict[str, str],
        budgets: Dict[str, int],
    ) -> tuple[Dict[str, str], Dict[str, Any]]:
        """对上下文各部分执行预算控制。

        Args:
            context_parts: 上下文各部分 {key: content}
            budgets: 各部分的 Token 预算 {key: max_tokens}

        Returns:
            (预算内的上下文, 预算执行报告)
        """
        result_parts = {}
        reports = {}
        total_tokens = 0
        total_truncated = 0

        for key, content in context_parts.items():
            max_tokens = budgets.get(key, 10000)  # 默认 10k tokens
            truncated_content, was_truncated = BudgetEnforcerService.truncate_to_budget(
                content, max_tokens
            )
            result_parts[key] = truncated_content

            tokens = BudgetEnforcerService.estimate_tokens(truncated_content)
            total_tokens += tokens
            if was_truncated:
                total_truncated += 1

            reports[key] = {
                "tokens": tokens,
                "max_tokens": max_tokens,
                "utilization": tokens / max_tokens if max_tokens > 0 else 0,
                "truncated": was_truncated,
            }

        summary = {
            "total_tokens": total_tokens,
            "total_parts": len(context_parts),
            "truncated_parts": total_truncated,
            "part_reports": reports,
        }

        return result_parts, summary

    @staticmethod
    def check_total_budget(
        total_tokens: int,
        max_context_tokens: int,
        warn_threshold: float = 0.8,
    ) -> Dict[str, Any]:
        """检查总体预算使用情况。

        Args:
            total_tokens: 当前总 Token 数
            max_context_tokens: 最大上下文 Token 数
            warn_threshold: 警告阈值（默认 80%）

        Returns:
            预算检查报告
        """
        utilization = total_tokens / max_context_tokens if max_context_tokens > 0 else 0

        status = "ok"
        if utilization >= 1.0:
            status = "exceeded"
        elif utilization >= warn_threshold:
            status = "warning"

        report = {
            "status": status,
            "total_tokens": total_tokens,
            "max_tokens": max_context_tokens,
            "utilization": utilization,
            "remaining_tokens": max(0, max_context_tokens - total_tokens),
        }

        if status == "warning":
            logger.warning(
                "上下文预算使用率达到 %.1f%% (%d/%d tokens)",
                utilization * 100,
                total_tokens,
                max_context_tokens,
            )
        elif status == "exceeded":
            logger.error(
                "上下文预算超限: %d tokens (预算: %d tokens)",
                total_tokens,
                max_context_tokens,
            )

        return report
