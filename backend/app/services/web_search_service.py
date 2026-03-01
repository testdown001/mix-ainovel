# AIMETA P=参考小说搜索服务_灵感模式联网检索|R=参考小说检索_结果糅合|NR=不含路由|E=WebSearchService|X=net|A=服务类|D=asyncio,llm|S=net,cache|RD=./README.ai
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .cache_service import CacheService
from .llm_service import LLMService

logger = logging.getLogger(__name__)


class WebSearchService:
    """参考小说网络搜索服务：并行检索 + 结果糅合 + 缓存。"""

    _MAX_REFERENCE_NOVELS = 3
    _CACHE_TTL_SECONDS = 24 * 60 * 60

    def __init__(self, session):
        self.session = session
        self.llm_service = LLMService(session)
        self.cache_service = CacheService()

    async def search_reference_novels(
        self,
        novel_names: List[str],
        *,
        user_id: int,
        project_id: Optional[str] = None,
    ) -> str:
        """搜索参考小说并返回可注入 system prompt 的 Markdown。"""
        normalized_names = self._normalize_novel_names(novel_names)
        if not normalized_names:
            return ""

        cache_key = self._build_cache_key(project_id=project_id, user_id=user_id, novel_names=normalized_names)
        cached = await self._get_cached_context(cache_key)
        if cached:
            logger.info(
                "参考小说搜索命中缓存: project_id=%s user_id=%s novels=%s",
                project_id,
                user_id,
                normalized_names,
            )
            return cached

        # 预校验搜索模型配置，未配置时由调用方决定是否降级
        await self.llm_service._resolve_search_llm_config()

        results = await asyncio.gather(
            *(self._search_single_novel(novel_name=name) for name in normalized_names),
            return_exceptions=True,
        )

        successful_results: List[Dict[str, str]] = []
        failed_novels: List[str] = []
        for index, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    "参考小说搜索失败: novel=%s project_id=%s user_id=%s error=%s",
                    normalized_names[index],
                    project_id,
                    user_id,
                    result,
                )
                failed_novels.append(normalized_names[index])
                continue
            successful_results.append(result)

        if not successful_results:
            raise HTTPException(status_code=502, detail="参考小说搜索失败，请检查搜索模型配置或稍后重试")

        fused_summary = await self._fuse_search_results(
            successful_results=successful_results,
            all_novel_names=normalized_names,
        )
        context = self._build_reference_context_markdown(
            fused_summary=fused_summary,
            successful_results=successful_results,
            failed_novels=failed_novels,
        )

        await self._set_cached_context(cache_key, context)
        return context

    async def _search_single_novel(self, *, novel_name: str) -> Dict[str, str]:
        query = f"起点中文网 番茄小说 {novel_name} 剧情 架构 大纲 角色 设定"
        system_prompt = (
            "你是小说资料检索助手。你必须优先使用联网搜索能力，聚焦起点中文网和番茄小说。"
            "如果目标站点信息不足，可补充其他中文站点。"
            "输出要求：\n"
            "1) 用中文回答；\n"
            "2) 先给出 4-8 条事实要点；\n"
            "3) 再给出“剧情结构/角色设计/世界观设定/节奏特点”四个小节；\n"
            "4) 内容只写可验证的公开信息，不要编造。"
        )
        user_prompt = (
            f"请搜索并总结这本小说：{novel_name}\n"
            f"推荐查询：{query}\n"
            "请尽量覆盖：题材定位、开篇钩子、主线推进方式、升级/冲突机制、角色关系网络。"
        )
        result = await self.llm_service.get_search_llm_response(
            system_prompt=system_prompt,
            conversation_history=[{"role": "user", "content": user_prompt}],
            temperature=0.3,
            timeout=180.0,
            max_tokens=2400,
        )
        return {"novel_name": novel_name, "query": query, "result": result.strip()}

    async def _fuse_search_results(
        self,
        *,
        successful_results: List[Dict[str, str]],
        all_novel_names: List[str],
    ) -> str:
        serialized = json.dumps(successful_results, ensure_ascii=False)
        system_prompt = (
            "你是资深网文策划编辑。请把多本参考小说的检索结果糅合成可执行的创作参考。"
            "输出必须是 Markdown，且按以下结构：\n"
            "## 叙事结构共性\n"
            "## 角色设计模式\n"
            "## 世界观与规则构建\n"
            "## 节奏与爽点编排\n"
            "## 可直接复用的创作建议（5-8条）\n"
            "## 风险与同质化提醒\n"
            "要求：结论导向、可操作、避免空话。"
        )
        user_prompt = (
            f"参考小说：{', '.join(all_novel_names)}\n"
            "以下是逐本搜索结果（JSON）：\n"
            f"{serialized}"
        )
        return await self.llm_service.get_search_llm_response(
            system_prompt=system_prompt,
            conversation_history=[{"role": "user", "content": user_prompt}],
            temperature=0.4,
            timeout=180.0,
            max_tokens=2800,
        )

    @classmethod
    def _normalize_novel_names(cls, novel_names: List[str]) -> List[str]:
        cleaned: List[str] = []
        for raw in novel_names[: cls._MAX_REFERENCE_NOVELS]:
            text = (raw or "").strip()
            if not text:
                continue
            if text in cleaned:
                continue
            cleaned.append(text)
        return cleaned

    @staticmethod
    def _build_reference_context_markdown(
        *,
        fused_summary: str,
        successful_results: List[Dict[str, str]],
        failed_novels: List[str],
    ) -> str:
        searched = "、".join(item["novel_name"] for item in successful_results)
        lines = [
            "## 参考小说搜索结果（自动注入）",
            f"- 已检索：{searched}",
        ]
        if failed_novels:
            lines.append(f"- 检索失败：{'、'.join(failed_novels)}（已自动忽略）")
        lines.append("")
        lines.append((fused_summary or "").strip())
        return "\n".join(lines).strip()

    @staticmethod
    def _build_cache_key(*, project_id: Optional[str], user_id: int, novel_names: List[str]) -> str:
        joined = json.dumps(novel_names, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()  # noqa: S324 - non-security hash
        scope = project_id or f"user-{user_id}"
        return f"reference_search:{scope}:{digest}"

    async def _get_cached_context(self, cache_key: str) -> Optional[str]:
        payload: Optional[Any] = await self.cache_service.get(cache_key)
        if isinstance(payload, dict):
            context = payload.get("reference_context")
            if isinstance(context, str) and context.strip():
                return context
        return None

    async def _set_cached_context(self, cache_key: str, reference_context: str) -> None:
        if not reference_context:
            return
        await self.cache_service.set(
            cache_key,
            {"reference_context": reference_context},
            expire=self._CACHE_TTL_SECONDS,
        )
