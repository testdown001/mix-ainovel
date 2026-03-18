# AIMETA P=mem0记忆蒸馏|R=合并/消歧/淘汰冗余记忆条目|E=distill
"""
记忆蒸馏服务 — 控制 mem0 记忆无限增长。

当条目数超过阈值时，使用轻量 LLM 将重复/冗余/过时的记忆合并或淘汰，
保持记忆池精炼可用。
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DISTILL_THRESHOLD = 100
DISTILL_BATCH_SIZE = 50

DISTILL_PROMPT = """你是记忆蒸馏专家。给定一组关于同一小说项目的事实性记忆条目，请：
1. 合并：同一事件/状态的多条记忆合并为一条精炼陈述
2. 消歧：矛盾条目保留最新的
3. 淘汰：被后续事件完全取代的过时条目
4. 压缩：冗长描述压缩为简练陈述

原则：宁可保留，不可误删。重大事件必须保留。

请分析以下记忆条目并返回纯 JSON（不要 markdown 代码块）：
{"kept": [{"id":"原始ID","memory":"文本"}], "merged": [{"ids":["源ID"],"memory":"合并后文本"}], "obsolete": [{"id":"ID","reason":"原因"}]}

记忆条目：
"""


class MemoryDistillationService:
    """mem0 记忆蒸馏：合并重复、消歧矛盾、淘汰过时。"""

    def __init__(self, llm_service):
        self.llm_service = llm_service
        self._memory = None

    async def _ensure_memory(self):
        """独立 AsyncMemory 实例，复用 MemoryLayerService 的配置构建。"""
        if self._memory is not None:
            return self._memory
        try:
            from mem0 import AsyncMemory
            from .memory_layer_service import MemoryLayerService

            config = MemoryLayerService._build_mem0_config()
            self._memory = AsyncMemory.from_config(config)
            return self._memory
        except Exception:
            logger.warning("记忆蒸馏: mem0 初始化失败", exc_info=True)
            return None

    async def should_distill(self, project_id: str) -> bool:
        """检查条目数是否达到蒸馏阈值。"""
        memory = await self._ensure_memory()
        if memory is None:
            return False
        try:
            result = await memory.get_all(user_id=f"novel_{project_id}", limit=DISTILL_THRESHOLD + 1)
            memories = result.get("results", []) if isinstance(result, dict) else result
            return len(memories) >= DISTILL_THRESHOLD
        except Exception:
            logger.warning("记忆蒸馏: 检查条目数失败", exc_info=True)
            return False

    async def distill(
        self,
        project_id: str,
        user_id: int,
        *,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """蒸馏主流程。

        1. 取全量记忆
        2. 分批调用 LLM 分析
        3. 删除 obsolete + merged 源，添加 merged 结果
        4. 返回统计
        """
        memory = await self._ensure_memory()
        if memory is None:
            return {"status": "skipped", "reason": "mem0_unavailable"}

        user_key = f"novel_{project_id}"

        try:
            result = await memory.get_all(user_id=user_key)
            all_memories = result.get("results", []) if isinstance(result, dict) else result
        except Exception:
            logger.exception("记忆蒸馏: 获取全量记忆失败 project=%s", project_id)
            return {"status": "error", "reason": "fetch_failed"}

        if not all_memories:
            return {"status": "skipped", "reason": "empty", "before": 0, "after": 0}

        before_count = len(all_memories)
        logger.info(
            "记忆蒸馏开始 project=%s count=%d (故障恢复: 蒸馏前全量记录)",
            project_id, before_count,
        )
        # 日志记录全量 facts 用于故障恢复
        for m in all_memories:
            logger.info("  [蒸馏前] id=%s memory=%s", m.get("id"), m.get("memory", "")[:200])

        total_kept = []
        total_merged = []
        total_obsolete = []

        # 分批处理
        for i in range(0, len(all_memories), DISTILL_BATCH_SIZE):
            batch = all_memories[i : i + DISTILL_BATCH_SIZE]
            batch_result = await self._distill_batch(batch, user_id)
            total_kept.extend(batch_result.get("kept", []))
            total_merged.extend(batch_result.get("merged", []))
            total_obsolete.extend(batch_result.get("obsolete", []))

        if dry_run:
            return {
                "status": "dry_run",
                "before": before_count,
                "kept": len(total_kept),
                "merged": len(total_merged),
                "obsolete": len(total_obsolete),
                "details": {
                    "merged": total_merged,
                    "obsolete": total_obsolete,
                },
            }

        # 执行删除和添加
        ids_to_delete = set()
        for obs in total_obsolete:
            if obs.get("id"):
                ids_to_delete.add(obs["id"])
        for merged in total_merged:
            for src_id in merged.get("ids", []):
                ids_to_delete.add(src_id)

        deleted_count = 0
        for mid in ids_to_delete:
            try:
                await memory.delete(mid)
                deleted_count += 1
            except Exception:
                logger.warning("记忆蒸馏: 删除 %s 失败", mid)

        added_count = 0
        for merged in total_merged:
            if merged.get("memory"):
                try:
                    await memory.add(merged["memory"], user_id=user_key)
                    added_count += 1
                except Exception:
                    logger.warning("记忆蒸馏: 添加合并记忆失败: %s", merged["memory"][:100])

        after_count = before_count - deleted_count + added_count
        logger.info(
            "记忆蒸馏完成 project=%s before=%d after=%d deleted=%d added=%d",
            project_id, before_count, after_count, deleted_count, added_count,
        )

        return {
            "status": "completed",
            "before": before_count,
            "after": after_count,
            "kept": len(total_kept),
            "merged": len(total_merged),
            "obsolete": len(total_obsolete),
        }

    async def _distill_batch(
        self,
        memories: List[Dict[str, Any]],
        user_id: int,
    ) -> Dict[str, Any]:
        """调用轻量 LLM 蒸馏单批次。未配置 grader 时返回全量 kept。"""
        # 检查 grader 是否可用
        if not hasattr(self.llm_service, "get_grader_llm_response"):
            return {"kept": memories, "merged": [], "obsolete": []}

        # 构建输入
        entries = []
        for m in memories:
            entries.append({"id": m.get("id", ""), "memory": m.get("memory", "")})

        prompt = DISTILL_PROMPT + json.dumps(entries, ensure_ascii=False, indent=1)

        try:
            response = await self.llm_service.get_grader_llm_response(
                system_prompt="你是记忆蒸馏专家。请严格按照 JSON 格式输出。",
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.1,
                user_id=user_id,
            )
        except Exception as e:
            err_str = str(e)
            if "grader" in err_str.lower() or "not configured" in err_str.lower():
                logger.info("记忆蒸馏: grader LLM 未配置，静默跳过")
                return {"kept": memories, "merged": [], "obsolete": []}
            logger.warning("记忆蒸馏: LLM 调用失败", exc_info=True)
            return {"kept": memories, "merged": [], "obsolete": []}

        # 解析 JSON
        try:
            content = response if isinstance(response, str) else str(response)
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(content[json_start:json_end])
                return {
                    "kept": parsed.get("kept", []),
                    "merged": parsed.get("merged", []),
                    "obsolete": parsed.get("obsolete", []),
                }
        except (json.JSONDecodeError, ValueError):
            logger.warning("记忆蒸馏: LLM 返回非法 JSON，全量保留")

        return {"kept": memories, "merged": [], "obsolete": []}
