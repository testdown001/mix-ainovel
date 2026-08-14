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

    # ------------------------------------------------------------------
    # 多维度检索：参考小说分析的输入侧
    # ------------------------------------------------------------------
    # 此前分析一本书只发一次检索（_search_single_novel，一段百科式摘要），几百万字的书
    # 压进 2400 token，三路抽取全吃同一段——「剧情思考不深」的根源在输入就没有料。
    # 现在按维度分别检索：每个维度有自己的检索意图与追问重点，抽取端各吃对应维度。
    # 单维度失败降级（少一路素材而已），全部失败才算检索失败。
    _SEARCH_DIMENSIONS: Dict[str, Dict[str, str]] = {
        "plot": {
            "query": "剧情 主线 分卷 结局 走向 剧情梳理",
            "focus": (
                "主线剧情的完整走向：开篇钩子、各卷/各阶段的核心目标与结局、"
                "关键转折点发生在故事的什么位置、结局怎么收。"
            ),
        },
        "characters": {
            "query": "角色 人物设定 人物关系 人物弧光",
            "focus": (
                "主要角色的身份、内在驱动、成长弧光；核心人物关系网络及其演变；"
                "反派的塑造方式与主角的对位关系。"
            ),
        },
        "beats": {
            "query": "名场面 经典桥段 高光情节 印象最深 高潮章节",
            "focus": (
                "这本书公认的名场面和经典桥段：每个桥段发生在什么局面下、"
                "前面怎么铺垫的、转折靠什么触发、读者的情绪在哪一刻兑现。"
                "尽量具体到情节细节，不要只给名字。"
            ),
        },
        "pacing": {
            "query": "爽点 节奏 追读 书评 分析",
            "focus": (
                "爽点的类型与分布密度、章节节奏（多少章一个小高潮、卷末怎么爆）、"
                "断章钩子的用法、读者对节奏的正负面评价。"
            ),
        },
        "craft": {
            "query": "文笔 写作手法 叙事视角 对白 书评",
            "focus": (
                "叙事视角与人称、句式与段落节奏、对白风格、描写密度、"
                "书评人对其写法的具体分析（优点与被诟病的点都要）。"
            ),
        },
    }

    async def search_novel_dimensions(
        self,
        *,
        novel_name: str,
        dimensions: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """按维度并行检索一本书，返回 {维度: 检索结果文本}（仅含成功的维度）。

        全部维度失败时抛 HTTPException 502；部分失败只记日志。
        每个维度的结果独立缓存 24h（重新分析时不必重付全部检索成本）。
        """
        wanted = [d for d in (dimensions or list(self._SEARCH_DIMENSIONS)) if d in self._SEARCH_DIMENSIONS]
        if not wanted:
            return {}

        # 预校验搜索通道配置：未配置时立刻 503，而不是 5 路各自失败
        await self.llm_service._resolve_search_llm_config()

        async def _one(dim: str) -> tuple[str, str]:
            cache_key = self._build_dimension_cache_key(novel_name=novel_name, dimension=dim)
            cached = await self.cache_service.get(cache_key)
            if isinstance(cached, dict) and isinstance(cached.get("result"), str) and cached["result"].strip():
                return dim, cached["result"]
            spec = self._SEARCH_DIMENSIONS[dim]
            query = f"起点中文网 番茄小说 {novel_name} {spec['query']}"
            system_prompt = (
                "你是小说资料检索助手。你必须优先使用联网搜索能力，聚焦起点中文网、番茄小说与中文书评社区。"
                "如果目标站点信息不足，可补充其他中文站点。"
                "输出要求：用中文；只写可验证的公开信息，不要编造；"
                "信息不足的点明确说「资料未提及」，不要用泛泛之谈填充。"
            )
            user_prompt = (
                f"请围绕一个明确的维度搜索并总结这本小说：{novel_name}\n"
                f"推荐查询：{query}\n"
                f"本次只关注：{spec['focus']}"
            )
            result = await self.llm_service.get_search_llm_response(
                system_prompt=system_prompt,
                conversation_history=[{"role": "user", "content": user_prompt}],
                temperature=0.3,
                timeout=180.0,
                max_tokens=2000,
            )
            text = result.strip()
            if text:
                await self.cache_service.set(cache_key, {"result": text}, expire=self._CACHE_TTL_SECONDS)
            return dim, text

        results = await asyncio.gather(*(_one(dim) for dim in wanted), return_exceptions=True)

        collected: Dict[str, str] = {}
        for index, item in enumerate(results):
            if isinstance(item, Exception):
                logger.warning(
                    "参考小说维度检索失败(降级): novel=%s dimension=%s error=%s",
                    novel_name, wanted[index], item,
                )
                continue
            dim, text = item
            if text:
                collected[dim] = text

        if not collected:
            raise HTTPException(status_code=502, detail="参考小说检索失败，请检查搜索模型配置或稍后重试")
        return collected

    @staticmethod
    def _build_dimension_cache_key(*, novel_name: str, dimension: str) -> str:
        digest = hashlib.sha1(novel_name.encode("utf-8")).hexdigest()  # noqa: S324 - non-security hash
        return f"reference_dim_search:{digest}:{dimension}"

    @staticmethod
    def combine_dimension_texts(dimension_results: Dict[str, str], *keys: str) -> str:
        """把若干维度的检索结果拼成一段抽取输入；请求的维度都缺失时回退全部可用维度。

        抽取端按需组合：大纲吃 plot+characters、桥段吃 beats+pacing+plot——
        而不是所有抽取路吃同一段大杂烩。
        """
        labels = {
            "plot": "主线剧情", "characters": "人物与关系", "beats": "名场面与桥段",
            "pacing": "节奏与爽点", "craft": "写法与文风",
        }
        picked = [(k, dimension_results[k]) for k in keys if dimension_results.get(k)]
        if not picked:
            picked = list(dimension_results.items())
        return "\n\n".join(f"【{labels.get(k, k)}】\n{text}" for k, text in picked)

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
