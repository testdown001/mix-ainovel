# AIMETA P=知识检索服务_两层RAG检索过滤|R=检索_过滤_注入|NR=不含向量库实现|E=KnowledgeRetrievalService|X=internal|A=检索_过滤_POV裁剪|D=llm_service_vector_store_service|S=none|RD=./README.ai
"""
知识检索服务 (KnowledgeRetrievalService)

融合自 AI_NovelGenerator 的知识检索设计，实现"检索→过滤→注入"的两层RAG：
1. 生成检索关键词 (query generation)
2. 向量检索 topK 相关内容
3. 知识过滤 (冲突检测/价值分级/结构化整理)
4. POV可见性裁剪 (配合有限视角)

这解决了"上下文太长塞不进 prompt"的问题，只注入最相关的过滤后内容。
"""
import logging
import inspect
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.init_db import repair_schema_if_needed
from ..models.project_memory import ProjectMemory
from ..models.chapter_blueprint import ChapterBlueprint
from .llm_service import LLMService
from .vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)


@dataclass
class RetrievedKnowledge:
    """检索到的知识片段"""
    content: str
    source: str  # chapter/setting/character/external
    relevance_score: float
    chapter_number: Optional[int] = None


@dataclass
class FilteredContext:
    """过滤后的上下文"""
    plot_fuel: List[str]  # 情节燃料
    character_info: List[str]  # 人物维度
    world_fragments: List[str]  # 世界碎片
    narrative_techniques: List[str]  # 叙事技法
    warnings: List[str]  # 冲突警告
    stats: Optional[Dict[str, Any]] = None


# ==================== 提示词模板 ====================

KNOWLEDGE_QUERY_PROMPT = """\
请基于以下当前写作需求，生成合适的知识库检索关键词：

章节元数据：
- 准备创作：第{chapter_number}章
- 章节主题：{chapter_title}
- 章节定位：{chapter_focus}
- 核心作用：{chapter_function}

写作目标：
- 悬念密度：{suspense_density}
- 伏笔操作：{foreshadowing_ops}
- 认知颠覆等级：{twist_level}

当前摘要：
{brief_summary}

用户指导（可能为空）：
{user_guidance}

生成规则：
1. 关键词组合逻辑：
   - 类型1：[实体]+[属性]（如"量子计算机 故障日志"）
   - 类型2：[事件]+[后果]（如"实验室爆炸 辐射泄漏"）
   - 类型3：[地点]+[特征]（如"地下城 氧气循环系统"）

2. 优先级：
   - 首选用户指导中明确提及的术语
   - 次选当前章节涉及的核心道具/地点
   - 最后补充可能关联的扩展概念

请生成3-5组检索词，按优先级降序排列。
格式：每组用"·"连接2-3个关键词，每组占一行

示例：
科技公司·数据泄露
地下实验室·基因编辑·禁忌实验
"""

KNOWLEDGE_FILTER_PROMPT = """\
对知识库检索内容进行三级过滤：

待过滤内容：
{retrieved_texts}

当前叙事需求：
- 章节号：第{chapter_number}章
- 章节功能：{chapter_function}
- 悬念密度：{suspense_density}
- POV角色：{pov_character}

前文摘要（用于检测重复）：
{global_summary}

过滤流程：

1. 冲突检测：
   - 删除与前文摘要重复度>40%的内容
   - 标记存在世界观矛盾的内容（使用▲前缀）

2. 价值评估：
   - 关键价值点（❗标记）：
     · 提供新的角色关系可能性
     · 包含可转化的隐喻素材
     · 存在至少2个可延伸的细节锚点
   - 次级价值点（·标记）：
     · 补充环境细节
     · 提供技术/流程描述

3. POV可见性过滤：
   - 仅保留POV角色{pov_character}能够知道/感知的信息
   - 移除POV角色不可能知道的秘密或他人内心活动

4. 结构重组：
   按"情节燃料/人物维度/世界碎片/叙事技法"分类

请以JSON格式返回过滤结果：
{{
  "plot_fuel": ["内容1", "内容2"],
  "character_info": ["内容1", "内容2"],
  "world_fragments": ["内容1", "内容2"],
  "narrative_techniques": ["内容1", "内容2"],
  "warnings": ["▲冲突警告1", "▲冲突警告2"]
}}

仅返回JSON，不要解释任何内容。
"""

SUMMARIZE_RECENT_CHAPTERS_PROMPT = """\
作为一名专业的小说编辑，请基于已完成的前几章内容生成当前章节的写作摘要。

前文内容：
{combined_text}

当前章节信息：
第{chapter_number}章《{chapter_title}》：
├── 本章定位：{chapter_focus}
├── 核心作用：{chapter_function}
├── 悬念密度：{suspense_density}
├── 伏笔操作：{foreshadowing_ops}
├── 认知颠覆：{twist_level}
└── 本章简述：{brief_summary}

请完成以下任务：
1. 用最多500字，写一个简洁明了的「当前章节写作摘要」
2. 突出与本章相关的前文要点
3. 标注需要延续的伏笔和人物状态

请按如下格式输出：
当前章节摘要: <这里写当前章节摘要>
"""


class KnowledgeRetrievalService:
    """
    知识检索服务
    
    实现两层RAG：检索→过滤→注入
    """
    
    def __init__(
        self,
        db: Session | AsyncSession,
        llm_service: LLMService,
        vector_store_service: Optional[VectorStoreService] = None
    ):
        self.db = db
        self.llm_service = llm_service
        self.vector_store_service = vector_store_service

    async def _execute_stmt(self, stmt):
        """统一执行 SQL 语句，兼容 Session / AsyncSession。"""
        try:
            result = self.db.execute(stmt)
            if inspect.isawaitable(result):
                return await result
            return result
        except OperationalError as exc:
            repaired = await repair_schema_if_needed(exc)
            if not repaired:
                raise
            result = self.db.execute(stmt)
            if inspect.isawaitable(result):
                return await result
            return result
    
    async def retrieve_and_filter(
        self,
        project_id: str,
        chapter_number: int,
        user_id: int,
        pov_character: Optional[str] = None,
        user_guidance: Optional[str] = None,
        top_k: int = 5,
        retrieval_mode: str = "vector",
        use_simple_mode: bool = False,
    ) -> FilteredContext:
        """
        检索并过滤知识
        
        Args:
            project_id: 项目ID
            chapter_number: 章节号
            user_id: 用户ID
            pov_character: POV角色（用于可见性过滤）
            user_guidance: 用户指导
            top_k: 检索数量
            retrieval_mode: 检索模式
            use_simple_mode: 简单模式 — 跳过 LLM 检索规划和过滤，
                             直接从蓝图提取关键词进行向量检索并按分数截断
            
        Returns:
            FilteredContext
        """
        # 1. 获取章节蓝图信息
        blueprint = await self._get_chapter_blueprint(project_id, chapter_number)

        if use_simple_mode:
            return await self._retrieve_simple(
                project_id=project_id,
                chapter_number=chapter_number,
                blueprint=blueprint,
                user_id=user_id,
                user_guidance=user_guidance,
                pov_character=pov_character,
                top_k=top_k,
                retrieval_mode=retrieval_mode,
            )

        # 2. P2: 智能检索规划（多源路由）
        plan = await self._plan_retrieval(blueprint, user_guidance, user_id)
        queries = plan.get("queries") or []
        sources = plan.get("sources") or ["vector_store"]

        # 如果规划失败，回退到原有关键词生成
        if not queries:
            queries = await self._generate_search_queries(
                blueprint=blueprint,
                user_guidance=user_guidance,
                user_id=user_id
            )
            sources = ["vector_store"]

        # 3. 多源检索
        retrieved: List[RetrievedKnowledge] = []

        if "vector_store" in sources:
            retrieved += await self._retrieve_from_vector_store(
                project_id=project_id,
                queries=queries,
                top_k=top_k,
                user_id=user_id,
                retrieval_mode=retrieval_mode,
            )

        if "character_state" in sources:
            state = await self._get_character_state(project_id)
            if state:
                retrieved.append(RetrievedKnowledge(
                    content=state, source="character_state", relevance_score=0.9,
                ))

        if "world_setting" in sources:
            ws = await self._get_world_setting(project_id)
            if ws:
                retrieved.append(RetrievedKnowledge(
                    content=ws, source="world_setting", relevance_score=0.85,
                ))

        # 4. P3: 查询反思 — 检索不足时补充检索
        if len(retrieved) < 3 and queries:
            extra_queries = await self._reflect_and_expand(
                plan, retrieved, blueprint, user_id
            )
            if extra_queries:
                retrieved += await self._retrieve_from_vector_store(
                    project_id=project_id,
                    queries=extra_queries,
                    top_k=top_k,
                    user_id=user_id,
                    retrieval_mode=retrieval_mode,
                )

        # 5. 获取前文摘要
        memory = await self._get_project_memory(project_id)
        global_summary = memory.global_summary if memory else ""

        # 6. 过滤和结构化
        filtered = await self._filter_knowledge(
            retrieved=retrieved,
            blueprint=blueprint,
            global_summary=global_summary,
            pov_character=pov_character,
            user_id=user_id
        )

        filtered_counts = {
            "plot_fuel": len(filtered.plot_fuel),
            "character_info": len(filtered.character_info),
            "world_fragments": len(filtered.world_fragments),
            "narrative_techniques": len(filtered.narrative_techniques),
            "warnings": len(filtered.warnings),
        }
        hit_chapters = sorted({r.chapter_number for r in retrieved if r.chapter_number})
        filtered.stats = {
            "query_count": len(queries),
            "retrieved_count": len(retrieved),
            "top_k": top_k,
            "hit_chapters": hit_chapters,
            "filtered_counts": filtered_counts,
            "total_filtered": sum(filtered_counts.values()),
            "pov_character": pov_character,
        }

        return filtered

    async def _retrieve_simple(
        self,
        project_id: str,
        chapter_number: int,
        blueprint: Optional[ChapterBlueprint],
        user_id: int,
        user_guidance: Optional[str],
        pov_character: Optional[str],
        top_k: int,
        retrieval_mode: str,
    ) -> FilteredContext:
        """简单检索模式：0 次 LLM 调用，从蓝图提取关键词 + 向量检索 + 分数截断。"""
        queries: List[str] = []
        if blueprint:
            for field in (blueprint.chapter_focus, blueprint.brief_summary, blueprint.chapter_function):
                if field:
                    queries.append(field)
        if user_guidance:
            queries.append(user_guidance)
        if not queries:
            queries = [f"第{chapter_number}章"]

        retrieved: List[RetrievedKnowledge] = []
        if self.vector_store_service:
            retrieved = await self._retrieve_from_vector_store(
                project_id=project_id,
                queries=queries[:3],
                top_k=top_k,
                user_id=user_id,
                retrieval_mode=retrieval_mode,
            )

        # 按分数截断（score > 0.5）代替 LLM 过滤
        MIN_RELEVANCE = 0.5
        retrieved = [r for r in retrieved if r.relevance_score >= MIN_RELEVANCE]

        # 简单分类：所有内容归入 plot_fuel
        plot_fuel = [r.content for r in retrieved]
        hit_chapters = sorted({r.chapter_number for r in retrieved if r.chapter_number})

        result = FilteredContext(
            plot_fuel=plot_fuel,
            character_info=[],
            world_fragments=[],
            narrative_techniques=[],
            warnings=[],
            stats={
                "query_count": len(queries),
                "retrieved_count": len(retrieved),
                "top_k": top_k,
                "hit_chapters": hit_chapters,
                "mode": "simple",
                "pov_character": pov_character,
            },
        )
        return result
    
    async def get_chapter_context(
        self,
        project_id: str,
        chapter_number: int,
        user_id: int,
        include_recent_chapters: int = 3,
        pov_character: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取章节写作上下文
        
        整合多个来源的信息，为章节生成提供完整上下文。
        """
        context = {}
        
        # 1. 获取项目记忆
        memory = await self._get_project_memory(project_id)
        
        if memory:
            context["global_summary"] = memory.global_summary
            context["plot_arcs"] = memory.plot_arcs
        
        # 2. 获取章节蓝图
        blueprint = await self._get_chapter_blueprint(project_id, chapter_number)
        if blueprint:
            context["blueprint"] = {
                "chapter_focus": blueprint.chapter_focus,
                "chapter_function": blueprint.chapter_function,
                "suspense_density": blueprint.suspense_density,
                "foreshadowing_ops": blueprint.foreshadowing_ops,
                "twist_level": blueprint.cognitive_twist_level,
                "brief_summary": blueprint.brief_summary,
                "mission_constraints": blueprint.mission_constraints
            }
        
        # 3. 获取前几章内容摘要
        if include_recent_chapters > 0:
            recent_summaries = await self._get_recent_chapter_summaries(
                project_id=project_id,
                current_chapter=chapter_number,
                count=include_recent_chapters
            )
            context["recent_chapters"] = recent_summaries
        
        # 4. 检索相关知识
        if self.vector_store_service:
            filtered = await self.retrieve_and_filter(
                project_id=project_id,
                chapter_number=chapter_number,
                user_id=user_id,
                pov_character=pov_character
            )
            context["filtered_knowledge"] = {
                "plot_fuel": filtered.plot_fuel,
                "character_info": filtered.character_info,
                "world_fragments": filtered.world_fragments,
                "narrative_techniques": filtered.narrative_techniques,
                "warnings": filtered.warnings
            }
        
        # 5. 获取角色状态
        character_state = await self._get_character_state(project_id)
        if character_state:
            context["character_state"] = character_state
        
        return context
    
    async def generate_chapter_summary(
        self,
        project_id: str,
        chapter_number: int,
        user_id: int
    ) -> Optional[str]:
        """
        生成当前章节的写作摘要
        
        基于前文内容和章节蓝图，生成针对性的写作摘要。
        """
        # 获取章节蓝图
        blueprint = await self._get_chapter_blueprint(project_id, chapter_number)
        if not blueprint:
            return None
        
        # 获取前几章内容
        recent_chapters = await self._get_recent_chapter_content(
            project_id=project_id,
            current_chapter=chapter_number,
            count=3
        )
        
        combined_text = "\n\n---\n\n".join([
            f"第{ch['number']}章：\n{ch['content'][:2000]}..."
            for ch in recent_chapters
        ])
        
        prompt = SUMMARIZE_RECENT_CHAPTERS_PROMPT.format(
            combined_text=combined_text,
            chapter_number=chapter_number,
            chapter_title=blueprint.brief_summary or f"第{chapter_number}章",
            chapter_focus=blueprint.chapter_focus or "",
            chapter_function=blueprint.chapter_function or "",
            suspense_density=blueprint.suspense_density or "",
            foreshadowing_ops=blueprint.foreshadowing_ops or "",
            twist_level=blueprint.cognitive_twist_level or 1,
            brief_summary=blueprint.brief_summary or ""
        )
        
        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                user_id=user_id,
                max_tokens=1000,
                temperature=0.3
            )
            return response.strip() if response else None
        except Exception as e:
            logger.error(f"生成章节摘要失败: {e}")
            return None
    
    async def _get_project_memory(self, project_id: str) -> Optional[ProjectMemory]:
        """获取项目记忆（兼容 AsyncSession / Session）。"""
        result = await self._execute_stmt(
            select(ProjectMemory).where(ProjectMemory.project_id == project_id)
        )
        return result.scalars().first()

    async def _get_chapter_blueprint(
        self,
        project_id: str,
        chapter_number: int
    ) -> Optional[ChapterBlueprint]:
        """获取章节蓝图"""
        result = await self._execute_stmt(
            select(ChapterBlueprint).where(
                ChapterBlueprint.project_id == project_id,
                ChapterBlueprint.chapter_number == chapter_number,
            )
        )
        return result.scalars().first()
    
    async def _generate_search_queries(
        self,
        blueprint: Optional[ChapterBlueprint],
        user_guidance: Optional[str],
        user_id: int
    ) -> List[str]:
        """生成检索关键词"""
        if not blueprint:
            return []
        
        prompt = KNOWLEDGE_QUERY_PROMPT.format(
            chapter_number=blueprint.chapter_number,
            chapter_title=blueprint.brief_summary or "",
            chapter_focus=blueprint.chapter_focus or "",
            chapter_function=blueprint.chapter_function or "",
            suspense_density=blueprint.suspense_density or "",
            foreshadowing_ops=blueprint.foreshadowing_ops or "",
            twist_level=blueprint.cognitive_twist_level or 1,
            brief_summary=blueprint.brief_summary or "",
            user_guidance=user_guidance or ""
        )
        
        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                user_id=user_id,
                max_tokens=500,
                temperature=0.5
            )
            
            if response:
                # 解析关键词
                queries = [
                    line.strip().replace("·", " ")
                    for line in response.strip().split("\n")
                    if line.strip()
                ]
                return queries[:5]
        except Exception as e:
            logger.error(f"生成检索关键词失败: {e}")
        
        return []
    
    async def _retrieve_from_vector_store(
        self,
        project_id: str,
        queries: List[str],
        top_k: int,
        user_id: int,
        retrieval_mode: str = "vector",
    ) -> List[RetrievedKnowledge]:
        """从向量库检索"""
        if not self.vector_store_service or not queries:
            return []

        retrieved = []
        for query in queries:
            try:
                # 混合检索模式
                if retrieval_mode == "hybrid":
                    embedding = await self.llm_service.get_embedding(query, user_id=user_id)
                    if not embedding:
                        continue
                    try:
                        from .hybrid_retrieval_service import HybridRetrievalService
                        hybrid = HybridRetrievalService(
                            vector_store=self.vector_store_service,
                            llm_service=self.llm_service,
                        )
                        hybrid_results = await hybrid.hybrid_search(
                            project_id=project_id,
                            query_text=query,
                            query_embedding=embedding,
                            top_k=top_k,
                            user_id=user_id,
                        )
                        for chunk in hybrid_results.get("chunks", []):
                            retrieved.append(RetrievedKnowledge(
                                content=chunk.content,
                                source="chapter",
                                relevance_score=chunk.score,
                                chapter_number=chunk.chapter_number,
                            ))
                        continue
                    except Exception as hybrid_exc:
                        logger.warning("混合检索失败，回退纯向量: %s", hybrid_exc)

                if hasattr(self.vector_store_service, "search"):
                    results = await self.vector_store_service.search(
                        project_id=project_id,
                        query=query,
                        top_k=top_k
                    )
                else:
                    embedding = await self.llm_service.get_embedding(query, user_id=user_id)
                    if not embedding:
                        continue
                    chunks = await self.vector_store_service.query_chunks(
                        project_id=project_id,
                        embedding=embedding,
                        top_k=top_k,
                    )
                    results = [
                        {
                            "content": chunk.content,
                            "source": "chapter",
                            "chapter_number": chunk.chapter_number,
                            "score": chunk.score,
                        }
                        for chunk in chunks
                    ]
                for r in results:
                    retrieved.append(RetrievedKnowledge(
                        content=r.get("content", ""),
                        source=r.get("source", "unknown"),
                        relevance_score=r.get("score", 0.0),
                        chapter_number=r.get("chapter_number")
                    ))
            except Exception as e:
                logger.error(f"向量检索失败: {e}")
        
        # 去重
        seen = set()
        unique = []
        for r in retrieved:
            if r.content not in seen:
                seen.add(r.content)
                unique.append(r)

        # P1: 统一 Rerank（不依赖 hybrid 模式）
        if unique and getattr(settings, "rag_reranker_enabled", False):
            unique = await self._rerank_results(queries[0] if queries else "", unique)

        return unique

    async def _rerank_results(
        self,
        query: str,
        results: List[RetrievedKnowledge],
    ) -> List[RetrievedKnowledge]:
        """调用外部 Reranker API 对检索结果精排。"""
        api_url = getattr(settings, "rag_reranker_api_url", None)
        api_key = getattr(settings, "rag_reranker_api_key", None)
        model = getattr(settings, "rag_reranker_model", "jina-reranker-v2-base-multilingual")

        if not api_url or not api_key:
            return results

        import httpx
        documents = [r.content[:500] for r in results]
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    str(api_url),
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": model, "query": query, "documents": documents, "top_n": len(documents)},
                )
                resp.raise_for_status()
                data = resp.json()

            reranked = []
            for item in sorted(data.get("results", []), key=lambda x: x.get("relevance_score", 0), reverse=True):
                idx = item.get("index", 0)
                if idx < len(results):
                    results[idx].relevance_score = item.get("relevance_score", results[idx].relevance_score)
                    reranked.append(results[idx])

            logger.info("Rerank 完成: %d → %d 结果", len(results), len(reranked))
            return reranked if reranked else results
        except Exception as exc:
            logger.warning("Rerank API 调用失败，保持原排序: %s", exc)
            return results
    
    async def _filter_knowledge(
        self,
        retrieved: List[RetrievedKnowledge],
        blueprint: Optional[ChapterBlueprint],
        global_summary: str,
        pov_character: Optional[str],
        user_id: int
    ) -> FilteredContext:
        """过滤知识"""
        if not retrieved:
            return FilteredContext(
                plot_fuel=[],
                character_info=[],
                world_fragments=[],
                narrative_techniques=[],
                warnings=[]
            )
        
        # 格式化检索内容
        retrieved_texts = "\n\n".join([
            f"[来源: {r.source}, 相关度: {r.relevance_score:.2f}]\n{r.content}"
            for r in retrieved[:10]
        ])
        
        prompt = KNOWLEDGE_FILTER_PROMPT.format(
            retrieved_texts=retrieved_texts,
            chapter_number=blueprint.chapter_number if blueprint else 0,
            chapter_function=blueprint.chapter_function if blueprint else "",
            suspense_density=blueprint.suspense_density if blueprint else "",
            pov_character=pov_character or "主角",
            global_summary=global_summary[:2000] if global_summary else ""
        )
        
        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                user_id=user_id,
                max_tokens=2000,
                temperature=0.3
            )
            
            if response:
                import json
                response = response.strip()
                if response.startswith("```"):
                    response = response.split("```")[1]
                    if response.startswith("json"):
                        response = response[4:]
                
                data = json.loads(response)
                return FilteredContext(
                    plot_fuel=data.get("plot_fuel", []),
                    character_info=data.get("character_info", []),
                    world_fragments=data.get("world_fragments", []),
                    narrative_techniques=data.get("narrative_techniques", []),
                    warnings=data.get("warnings", [])
                )
        except Exception as e:
            logger.error(f"过滤知识失败: {e}")
        
        return FilteredContext(
            plot_fuel=[],
            character_info=[],
            world_fragments=[],
            narrative_techniques=[],
            warnings=[]
        )
    
    async def _get_recent_chapter_summaries(
        self,
        project_id: str,
        current_chapter: int,
        count: int
    ) -> List[Dict[str, Any]]:
        """获取前几章摘要"""
        from ..models.project_memory import ChapterSnapshot

        result = await self._execute_stmt(
            select(ChapterSnapshot)
            .where(
                ChapterSnapshot.project_id == project_id,
                ChapterSnapshot.chapter_number < current_chapter,
            )
            .order_by(ChapterSnapshot.chapter_number.desc())
            .limit(count)
        )
        snapshots = result.scalars().all()
        
        return [
            {
                "chapter_number": s.chapter_number,
                "summary": s.chapter_summary
            }
            for s in reversed(snapshots)
        ]
    
    async def _get_recent_chapter_content(
        self,
        project_id: str,
        current_chapter: int,
        count: int
    ) -> List[Dict[str, Any]]:
        """获取前几章内容"""
        from ..models.novel import Chapter, ChapterVersion
        from sqlalchemy.orm import selectinload
        result = await self._execute_stmt(
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number < current_chapter,
            )
            .options(
                selectinload(Chapter.selected_version),
                selectinload(Chapter.versions),
            )
            .order_by(Chapter.chapter_number.desc())
            .limit(count)
        )
        chapters = result.scalars().all()
        
        result = []
        for ch in reversed(chapters):
            content = ""
            if ch.selected_version:
                content = ch.selected_version.content
            elif ch.versions:
                content = ch.versions[-1].content
            
            result.append({
                "number": ch.chapter_number,
                "content": content
            })
        
        return result
    
    async def _get_character_state(self, project_id: str) -> Optional[str]:
        """获取角色状态"""
        from ..models.memory_layer import CharacterState
        result = await self._execute_stmt(
            select(CharacterState)
            .where(
                CharacterState.project_id == project_id,
                CharacterState.character_name == "__all__",
            )
            .order_by(CharacterState.chapter_number.desc())
        )
        states = result.scalars().first()
        
        if states and states.extra:
            return states.extra.get("raw_state_text")

        return None

    async def _get_world_setting(self, project_id: str) -> Optional[str]:
        """从蓝图中提取世界观设定文本。"""
        import json
        from ..models.novel import NovelBlueprint
        result = await self._execute_stmt(
            select(NovelBlueprint).where(NovelBlueprint.project_id == project_id)
        )
        bp = result.scalars().first()
        if bp and bp.world_setting:
            ws = bp.world_setting
            if isinstance(ws, dict):
                return json.dumps(ws, ensure_ascii=False)[:1000]
            return str(ws)[:1000]
        return None

    async def _plan_retrieval(
        self,
        blueprint: Optional[ChapterBlueprint],
        user_guidance: Optional[str],
        user_id: int,
    ) -> Dict[str, Any]:
        """P2: 智能检索规划 — 决定查询关键词和知识源。"""
        if not blueprint:
            return {"queries": [], "sources": ["vector_store"]}

        prompt = f"""你是小说知识检索规划器。根据章节需求决定检索策略。

章节信息：
- 第{blueprint.chapter_number}章
- 定位：{blueprint.chapter_focus or ''}
- 功能：{blueprint.chapter_function or ''}
- 简述：{blueprint.brief_summary or ''}

用户指导：{user_guidance or '无'}

请输出 JSON（不要 markdown 包裹）：
{{
  "queries": ["关键词1 关键词2", "关键词3 关键词4"],
  "sources": ["vector_store", "character_state", "world_setting"]
}}

规则：
- queries: 3-5组检索词，每组2-3个词用空格连接
- sources 从以下选择（至少包含 vector_store）：
  - vector_store: 前文情节片段（始终需要）
  - character_state: 涉及角色状态变化时选择
  - world_setting: 涉及世界观/地理/规则时选择
仅返回JSON。"""

        try:
            import json
            from ..utils.json_utils import remove_think_tags, unwrap_markdown_json, repair_json
            raw = await self.llm_service.generate(
                prompt=prompt, user_id=user_id, max_tokens=500, temperature=0.3,
            )
            cleaned = unwrap_markdown_json(remove_think_tags(raw))
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                return json.loads(repair_json(cleaned))
        except Exception as e:
            logger.warning("检索规划失败，回退默认: %s", e)
            return {"queries": [], "sources": ["vector_store"]}

    async def _reflect_and_expand(
        self,
        plan: Dict[str, Any],
        retrieved: List[RetrievedKnowledge],
        blueprint: Optional[ChapterBlueprint],
        user_id: int,
    ) -> List[str]:
        """P3: 查询反思 — 检索结果不足时生成补充关键词。"""
        if not blueprint:
            return []

        existing = "\n".join(f"- {r.content[:100]}" for r in retrieved[:5]) or "无"

        prompt = f"""检索结果不足，请生成补充检索词。

章节：第{blueprint.chapter_number}章 - {blueprint.brief_summary or ''}
原始检索词：{', '.join(plan.get('queries', []))}
已检索到的内容：
{existing}

请生成2-3组补充检索词（与原始词不同的角度），每行一组，用空格连接关键词。
仅输出检索词，不要解释。"""

        try:
            raw = await self.llm_service.generate(
                prompt=prompt, user_id=user_id, max_tokens=200, temperature=0.5,
            )
            if raw:
                return [l.strip() for l in raw.strip().split("\n") if l.strip()][:3]
        except Exception as e:
            logger.warning("查询反思失败: %s", e)
        return []
