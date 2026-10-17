"""
记忆层服务 (集成 mem0 AsyncMemory)

提供角色状态追踪、时间线管理、因果链维护的核心功能，
并使用 mem0 AsyncMemory 提供长期、跨章节的非结构化事实记忆检索池。"""
from typing import Optional, List, Dict, Any
import asyncio
import json
import logging
import os
from datetime import datetime

from mem0 import AsyncMemory
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func

from ..core.config import settings
from ..models.memory_layer import (
    CharacterState,
    TimelineEvent,
    CausalChain,
    StoryTimeTracker
)
from ..repositories.system_config_repository import SystemConfigRepository
from ..utils.json_utils import parse_llm_json
from .llm_service import LLMService
from .prompt_service import PromptService
from .memory_provenance import (
    filter_current_rows, filter_mem0_results, require_current_source, source_payload,
)

logger = logging.getLogger(__name__)


class MemoryLayerService:
    """基于 mem0 AsyncMemory 的记忆层服务"""

    def __init__(
        self,
        db: AsyncSession,
        llm_service: Optional[LLMService] = None,
        prompt_service: Optional[PromptService] = None,
    ):
        self.db = db
        self.llm_service = llm_service
        self.prompt_service = prompt_service
        self._memory: Optional[AsyncMemory] = None
        self._source_ref = None

    async def _cfg(self, key: str) -> Optional[str]:
        """按全系统统一口径解析通道配置：SystemConfig 优先，env 兜底。

        与 LLMService._get_config_value_for_session 同规则（env 键 = 大写并把 . 换成 _）。
        mem0 曾是全系统唯一直读 settings.* 的 LLM 出口，而 env 按约定只是首次启动的种子
        值——线上后台改过 key 后 env 仍是占位符，导致 mem0 恒 401、长期记忆全废。
        """
        record = await SystemConfigRepository(self.db).get_by_key(key)
        if record and record.value:
            return record.value
        return os.getenv(key.upper().replace(".", "_")) or None

    async def _build_mem0_config(self) -> dict:
        """构建 mem0 配置字典（通道参数走 SystemConfig）。"""
        qdrant_config: Dict[str, Any] = {
            "host": settings.qdrant_host,
            "port": settings.qdrant_port,
        }
        if settings.qdrant_api_key:
            qdrant_config["api_key"] = settings.qdrant_api_key

        llm_key = await self._cfg("llm.api_key")
        llm_base_url = await self._cfg("llm.base_url")
        llm_model = await self._cfg("llm.model")

        embed_key = await self._cfg("embedding.api_key") or llm_key
        # Embedder base_url：优先专用 embedding 通道，否则回退 LLM 通道
        embed_base_url = await self._cfg("embedding.base_url") or llm_base_url
        embed_model = await self._cfg("embedding.model")

        embedder_config: Dict[str, Any] = {
            "model": embed_model or settings.embedding_model,
            "api_key": embed_key,
            "openai_base_url": embed_base_url,
        }

        # 必须显式告知 mem0 实际向量维度：QdrantConfig.embedding_model_dims 默认 1536，
        # mem0 会按该默认值建自己的 collection，而本项目的 embedding 模型未必是 1536 维
        # （实测 jina-clip-v2 为 1024）→ mem0 每次读写都被 Qdrant 以 400 拒绝
        # "Vector dimension error: expected dim: 1536, got 1024"，长期记忆全废且静默。
        # 维度未知时不填，保留 mem0 自身默认，不做臆测。
        dims = await self._cfg("embedding.model_vector_size")
        vector_dims = None
        try:
            vector_dims = int(dims) if dims else settings.embedding_model_vector_size
        except (TypeError, ValueError):
            vector_dims = settings.embedding_model_vector_size
        if vector_dims:
            qdrant_config["embedding_model_dims"] = int(vector_dims)
            embedder_config["embedding_dims"] = int(vector_dims)

        return {
            "graph_store": None,
            "vector_store": {
                "provider": "qdrant",
                "config": qdrant_config,
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": llm_model or settings.openai_model_name,
                    "api_key": llm_key,
                    "openai_base_url": llm_base_url,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": embedder_config,
            },
        }

    async def _ensure_memory(self) -> AsyncMemory:
        """异步延迟初始化 AsyncMemory 实例，缓存到实例属性。"""
        if self._memory is None:
            from .mem0_compat import ProvenanceMemory
            config = await self._build_mem0_config()
            logger.info("初始化 mem0 AsyncMemory 实例...")
            self._memory = await ProvenanceMemory.from_config(config_dict=config)
        return self._memory

    # ===== 角色状态管理 =====

    async def get_character_state(
        self, 
        project_id: str, 
        character_name: str, 
        chapter_number: Optional[int] = None,
        *, allow_legacy: bool = False,
    ) -> Optional[CharacterState]:
        """获取角色在指定章节的状态（默认最新）"""
        query = select(CharacterState).where(
            and_(
                CharacterState.project_id == project_id,
                CharacterState.character_name == character_name
            )
        )
        
        if chapter_number is not None:
            query = query.where(CharacterState.chapter_number <= chapter_number)
        
        query = query.order_by(desc(CharacterState.chapter_number), desc(CharacterState.id))
        
        result = await self.db.execute(query)
        rows = list(result.scalars().all())
        if not allow_legacy:
            before = chapter_number + 1 if chapter_number is not None else max(
                (int(row.chapter_number) for row in rows), default=0,
            ) + 1
            rows = await filter_current_rows(self.db, rows, project_id, before)
        return rows[0] if rows else None

    async def get_all_character_states(
        self,
        project_id: str,
        chapter_number: int,
    ) -> List[CharacterState]:
        """Pick the latest *valid* snapshot per character, after provenance filtering.

        A newer draft/legacy row must not hide an older adopted state. Stable ID
        ordering also prevents duplicate rows from one chapter entering the prompt.
        """
        query = (select(CharacterState).where(
            CharacterState.project_id == project_id,
            CharacterState.chapter_number <= chapter_number,
        ).order_by(desc(CharacterState.chapter_number), desc(CharacterState.id)))
        result = await self.db.execute(query)
        rows = await filter_current_rows(
            self.db, list(result.scalars().all()), project_id, chapter_number + 1,
        )
        latest = {}
        for row in rows:
            latest.setdefault(row.character_name, row)
        return list(latest.values())

    async def _safe_rollback(self) -> None:
        """异常后复位共享 session（可能已处于待回滚状态）。

        与 TemporalStateService._safe_rollback 同义：不复位则同 session 的后续写入
        全部连带失败，各步骤之间的"独立错误隔离"形同虚设。
        """
        try:
            await self.db.rollback()
        except Exception:
            pass

    async def _extraction_checkpoint(self, name: str, producer):
        """Persist completed extraction before materialization, so retries reuse it."""
        from ..models.chapter_derivation import ChapterDerivationJob
        raw = source_payload(self._source_ref)
        job_id = raw.get("source_derivation_id")
        job = await self.db.get(ChapterDerivationJob, job_id) if job_id else None
        key = "extraction_" + name
        if isinstance(job, ChapterDerivationJob) and key in (job.result or {}):
            return job.result[key]
        value = await producer()
        if isinstance(job, ChapterDerivationJob):
            await require_current_source(self.db, self._source_ref)
            job.result = {**(job.result or {}), key: value}
            await self.db.commit()
        return value

    async def update_character_state(
        self,
        project_id: str,
        character_name: str,
        chapter_number: int,
        state_updates: Dict[str, Any],
        character_id: Optional[int] = None
    ) -> CharacterState:
        """更新角色状态（创建新的状态快照）"""
        # 获取上一章的状态作为基础
        prev_state = await self.get_character_state(
            project_id, character_name, chapter_number - 1, allow_legacy=self._source_ref is None,
        )
        
        # 创建新状态
        await require_current_source(self.db, self._source_ref)
        provenance = source_payload(self._source_ref)
        if provenance.get("source_derivation_id"):
            existing = (await self.db.execute(select(CharacterState).where(
                CharacterState.project_id == project_id, CharacterState.chapter_number == chapter_number,
                CharacterState.character_name == character_name,
            ))).scalars().all()
            for state in existing:
                if (state.extra or {}).get("provenance", {}).get("source_derivation_id") == provenance["source_derivation_id"]:
                    return state
        new_state = CharacterState(
            project_id=project_id,
            character_id=character_id or (prev_state.character_id if prev_state else None),
            character_name=character_name,
            chapter_number=chapter_number,
            # 继承上一章的状态
            location=prev_state.location if prev_state else None,
            emotion=prev_state.emotion if prev_state else None,
            emotion_intensity=prev_state.emotion_intensity if prev_state else None,
            health_status=prev_state.health_status if prev_state else "healthy",
            inventory=prev_state.inventory if prev_state else [],
            power_level=prev_state.power_level if prev_state else None,
            known_secrets=prev_state.known_secrets if prev_state else [],
            current_goals=prev_state.current_goals if prev_state else [],
        )
        
        # 应用更新
        for key, value in state_updates.items():
            if key not in {"id", "project_id", "chapter_number", "character_id", "extra"} and hasattr(new_state, key):
                setattr(new_state, key, value)
        if self._source_ref is not None:
            new_state.extra = {"provenance": source_payload(self._source_ref)}
        
        self.db.add(new_state)
        if self._source_ref is not None:
            await self.db.flush()
        else:
            await self.db.commit()
        await self.db.refresh(new_state)
        return new_state

    async def extract_character_states_from_chapter(
        self,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        character_names: List[str],
        user_id: int
    ) -> List[Dict[str, Any]]:
        """从章节内容中提取角色状态变化"""
        prompt = f"""分析以下章节内容，提取每个角色的状态变化。

[章节内容]
{chapter_content[:8000]}

[需要追踪的角色]
{json.dumps(character_names, ensure_ascii=False)}

请以 JSON 格式输出每个角色的状态变化：
```json
{{
  "character_states": [
    {{
      "character_name": "角色名",
      "location": "当前位置",
      "emotion": "主要情绪",
      "emotion_intensity": 1-10,
      "emotion_reason": "情绪原因",
      "health_status": "healthy/injured/critical",
      "injuries": ["受伤描述"],
      "inventory_changes": {{"gained": ["获得物品"], "lost": ["失去物品"]}},
      "relationship_changes": [{{"target": "对象", "change": "变化描述"}}],
      "new_knowledge": ["新获得的信息"],
      "goal_progress": [{{"goal": "目标", "progress": "进展"}}]
    }}
  ]
}}
```

只输出在本章中有变化或出场的角色。"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一个专业的小说分析助手，负责追踪角色状态变化。请严格按照 JSON 格式输出。",
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.2,
                user_id=user_id,
                timeout=120.0
            )
            
            # 解析 JSON（统一健壮解析）
            result = parse_llm_json(response, default=None)
            if isinstance(result, dict):
                return result.get("character_states", [])
        except Exception as e:
            logger.warning(f"提取角色状态失败: {e}")
            if self._source_ref is not None:
                raise
        
        return []

    # ===== 时间线管理 =====

    async def get_timeline(
        self, 
        project_id: str, 
        start_chapter: Optional[int] = None,
        end_chapter: Optional[int] = None
    ) -> List[TimelineEvent]:
        """获取时间线事件"""
        query = select(TimelineEvent).where(TimelineEvent.project_id == project_id)
        
        if start_chapter:
            query = query.where(TimelineEvent.chapter_number >= start_chapter)
        if end_chapter:
            query = query.where(TimelineEvent.chapter_number <= end_chapter)
        
        query = query.order_by(TimelineEvent.chapter_number, TimelineEvent.id)
        
        result = await self.db.execute(query)
        rows = list(result.scalars().all())
        if end_chapter is not None:
            rows = await filter_current_rows(self.db, rows, project_id, end_chapter + 1)
        return rows

    async def add_timeline_event(
        self,
        project_id: str,
        chapter_number: int,
        event_title: str,
        event_description: str,
        event_type: str = "minor",
        story_time: Optional[str] = None,
        involved_characters: Optional[List[str]] = None,
        location: Optional[str] = None,
        importance: int = 5,
        is_turning_point: bool = False
    ) -> TimelineEvent:
        """添加时间线事件"""
        await require_current_source(self.db, self._source_ref)
        provenance = source_payload(self._source_ref)
        if provenance.get("source_derivation_id"):
            existing = (await self.db.execute(select(TimelineEvent).where(
                TimelineEvent.project_id == project_id, TimelineEvent.chapter_number == chapter_number,
                TimelineEvent.event_title == event_title,
            ))).scalars().all()
            for item in existing:
                if (item.extra or {}).get("provenance", {}).get("source_derivation_id") == provenance["source_derivation_id"]:
                    return item
        event = TimelineEvent(
            project_id=project_id,
            chapter_number=chapter_number,
            event_title=event_title,
            event_description=event_description,
            event_type=event_type,
            story_time=story_time,
            involved_characters=involved_characters,
            location=location,
            importance=importance,
            is_turning_point=is_turning_point
        )
        self.db.add(event)
        if self._source_ref is not None:
            event.extra = {"provenance": source_payload(self._source_ref)}
            await self.db.flush()
        else:
            await self.db.commit()
        await self.db.refresh(event)
        return event

    async def extract_timeline_events_from_chapter(
        self,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """从章节内容中提取时间线事件"""
        prompt = f"""分析以下章节内容，提取关键事件。

[章节内容]
{chapter_content[:8000]}

请以 JSON 格式输出关键事件：
```json
{{
  "events": [
    {{
      "event_title": "事件标题（简短）",
      "event_description": "事件描述",
      "event_type": "major/minor/background",
      "story_time": "故事内时间（如'第三天早上'）",
      "involved_characters": ["涉及角色"],
      "location": "发生地点",
      "importance": 1-10,
      "is_turning_point": true/false
    }}
  ]
}}
```

只提取重要事件，不要列出琐碎细节。"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一个专业的小说分析助手，负责提取关键事件。请严格按照 JSON 格式输出。",
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.2,
                user_id=user_id,
                timeout=120.0
            )
            
            result = parse_llm_json(response, default=None)
            if isinstance(result, dict):
                return result.get("events", [])
        except Exception as e:
            logger.warning(f"提取时间线事件失败: {e}")
            if self._source_ref is not None:
                raise
        
        return []

    # ===== 因果链管理 =====

    async def get_pending_causal_chains(self, project_id: str, before_chapter: Optional[int] = None) -> List[CausalChain]:
        """获取待解决的因果链"""
        query = select(CausalChain).where(
                and_(
                    CausalChain.project_id == project_id,
                    CausalChain.status == "pending"
                )
            ).order_by(CausalChain.cause_chapter)
        if before_chapter is not None:
            query = query.where(CausalChain.cause_chapter < before_chapter)
        result = await self.db.execute(query)
        rows = list(result.scalars().all())
        if before_chapter is not None:
            rows = await filter_current_rows(self.db, rows, project_id, before_chapter)
        return rows

    async def build_chapter_state_context(
        self,
        project_id: str,
        chapter_number: int,
        involved_characters: Optional[List[str]] = None,
    ) -> Optional[str]:
        """构建章节状态上下文（纯DB查询，零LLM调用，延迟<100ms）。

        查询角色状态、近3章重大事件、待解决因果链，格式化为精简文本注入生成prompt。
        """
        parts: List[str] = []

        # 1. 角色当前状态
        try:
            states = await self.get_all_character_states(project_id, chapter_number - 1)
            if involved_characters:
                # 优先展示本章涉及角色，其余角色简略
                involved_set = set(involved_characters)
                primary = [s for s in states if s.character_name in involved_set]
                secondary = [s for s in states if s.character_name not in involved_set]
            else:
                primary = states
                secondary = []

            if primary:
                lines = []
                for s in primary[:8]:
                    info = f"{s.character_name}："
                    details = []
                    if s.location:
                        details.append(f"位于{s.location}")
                    if s.emotion:
                        details.append(f"情绪{s.emotion}")
                    if s.health_status and s.health_status != "正常":
                        details.append(f"状态{s.health_status}")
                    if s.power_level:
                        details.append(f"实力{s.power_level}")
                    if s.current_goals:
                        goals = s.current_goals if isinstance(s.current_goals, str) else "、".join(s.current_goals[:2])
                        details.append(f"目标：{goals}")
                    info += "，".join(details) if details else "无特殊状态"
                    lines.append(info)
                if secondary:
                    for s in secondary[:4]:
                        lines.append(f"{s.character_name}：位于{s.location or '未知'}")
                parts.append("【角色状态】\n" + "\n".join(lines))
        except Exception as e:
            logger.warning("构建角色状态上下文失败: %s", e)

        # 2. 近3章重大事件
        try:
            start_ch = max(1, chapter_number - 3)
            timeline = await self.get_timeline(project_id, start_chapter=start_ch, end_chapter=chapter_number - 1)
            major_events = [e for e in timeline if e.event_type == "major" or (e.importance and e.importance >= 7)]
            if major_events:
                event_lines = []
                for e in major_events[:5]:
                    event_lines.append(f"第{e.chapter_number}章：{e.event_title}")
                parts.append("【近期关键事件】\n" + "\n".join(event_lines))
        except Exception as e:
            logger.warning("构建时间线上下文失败: %s", e)

        # 3. 待解决因果链（top-3）
        try:
            chains = await self.get_pending_causal_chains(project_id, before_chapter=chapter_number)
            if chains:
                chain_lines = []
                for c in chains[:3]:
                    chain_lines.append(f"第{c.cause_chapter}章{c.cause_description} → 待解决：{c.effect_description}")
                parts.append("【待解决因果链】\n" + "\n".join(chain_lines))
        except Exception as e:
            logger.warning("构建因果链上下文失败: %s", e)

        if not parts:
            return None
        return "\n\n".join(parts)

    async def add_causal_chain(
        self,
        project_id: str,
        cause_description: str,
        cause_chapter: int,
        effect_description: str,
        cause_type: str = "event",
        effect_type: str = "event",
        involved_characters: Optional[List[str]] = None,
        importance: int = 5
    ) -> CausalChain:
        """添加因果链"""
        chain = CausalChain(
            project_id=project_id,
            cause_type=cause_type,
            cause_description=cause_description,
            cause_chapter=cause_chapter,
            effect_type=effect_type,
            effect_description=effect_description,
            involved_characters=involved_characters,
            importance=importance,
            status="pending"
        )
        self.db.add(chain)
        await self.db.commit()
        await self.db.refresh(chain)
        return chain

    async def resolve_causal_chain(
        self,
        chain_id: int,
        effect_chapter: int,
        resolution_description: str
    ) -> Optional[CausalChain]:
        """解决因果链"""
        result = await self.db.execute(
            select(CausalChain).where(CausalChain.id == chain_id)
        )
        chain = result.scalar_one_or_none()
        
        if chain:
            chain.status = "resolved"
            chain.effect_chapter = effect_chapter
            chain.resolution_description = resolution_description
            await self.db.commit()
            await self.db.refresh(chain)
        
        return chain

    # ===== 故事时间追踪 =====

    async def get_or_create_time_tracker(self, project_id: str) -> StoryTimeTracker:
        """获取或创建故事时间追踪器"""
        result = await self.db.execute(
            select(StoryTimeTracker).where(StoryTimeTracker.project_id == project_id)
        )
        tracker = result.scalar_one_or_none()
        
        if not tracker:
            tracker = StoryTimeTracker(
                project_id=project_id,
                chapter_time_map={}
            )
            self.db.add(tracker)
            await self.db.commit()
            await self.db.refresh(tracker)
        
        return tracker

    async def update_chapter_time(
        self,
        project_id: str,
        chapter_number: int,
        start_time: str,
        end_time: str,
        duration: str
    ) -> StoryTimeTracker:
        """更新章节时间"""
        await require_current_source(self.db, self._source_ref)
        tracker = await self.get_or_create_time_tracker(project_id)
        
        chapter_time_map = tracker.chapter_time_map or {}
        chapter_time_map[str(chapter_number)] = {
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration
        }
        tracker.chapter_time_map = chapter_time_map
        tracker.current_time = end_time
        if self._source_ref is not None:
            extra = dict(tracker.extra or {})
            extra["chapter_sources"] = {**extra.get("chapter_sources", {}),
                                        str(chapter_number): source_payload(self._source_ref)}
            tracker.extra = extra
        
        await self.db.commit()
        await self.db.refresh(tracker)
        return tracker

    # ===== 综合上下文生成 =====

    async def get_memory_context(
        self,
        project_id: str,
        chapter_number: int,
        involved_characters: Optional[List[str]] = None
    ) -> str:
        """生成记忆层上下文（用于注入到写作提示词） - 现含长期记忆(mem0)检索"""
        lines = ["# 记忆层上下文\n"]
        
        # 1. 角色状态
        character_states = await self.get_all_character_states(project_id, chapter_number - 1)
        if character_states:
            lines.append("## 角色当前状态\n")
            for state in character_states:
                if involved_characters and state.character_name not in involved_characters:
                    continue
                lines.append(f"### {state.character_name}")
                if state.location:
                    lines.append(f"- 位置：{state.location}")
                if state.emotion:
                    lines.append(f"- 情绪：{state.emotion}（强度 {state.emotion_intensity}/10）")
                if state.health_status and state.health_status != "healthy":
                    lines.append(f"- 健康：{state.health_status}")
                if state.current_goals:
                    lines.append(f"- 当前目标：{', '.join(state.current_goals[:3])}")
                lines.append("")
        
        # 2. 最近事件
        recent_events = await self.get_timeline(
            project_id, 
            start_chapter=max(1, chapter_number - 5),
            end_chapter=chapter_number - 1
        )
        if recent_events:
            lines.append("## 最近事件\n")
            for event in recent_events[-10:]:  # 最多显示 10 个
                lines.append(f"- 第{event.chapter_number}章：{event.event_title}")
                if event.is_turning_point:
                    lines.append("  （转折点）")
            lines.append("")
        
        # 3. 待解决的因果链
        pending_chains = await self.get_pending_causal_chains(project_id, before_chapter=chapter_number)
        if pending_chains:
            lines.append("## 待解决的因果链\n")
            for chain in pending_chains[:5]:  # 最多显示 5 个
                lines.append(f"- 【第{chain.cause_chapter}章】{chain.cause_description}")
                lines.append(f"  → 预期效果：{chain.effect_description}")
            lines.append("")
        
        # 4. 故事时间
        tracker = (await self.db.execute(select(StoryTimeTracker).where(
            StoryTimeTracker.project_id == project_id,
        ))).scalar_one_or_none()
        time_value = None
        if tracker is not None:
            from .memory_provenance import valid_provenance
            extra = tracker.extra if isinstance(getattr(tracker, "extra", None), dict) else {}
            mapping = tracker.chapter_time_map if isinstance(tracker.chapter_time_map, dict) else {}
            for number in sorted((int(n) for n in mapping if str(n).isdigit() and int(n) < chapter_number), reverse=True):
                if await valid_provenance(self.db, extra.get("chapter_sources", {}).get(str(number)), project_id, chapter_number):
                    time_value = mapping[str(number)].get("end_time")
                    break
        if time_value:
            lines.append("## 故事时间\n")
            lines.append(f"- 当前时间：{time_value}")
            lines.append("")

        # 5. Mem0 长期记忆检索
        lines.append("## 长期核心记忆 (mem0)\n")
        query_parts = []
        if involved_characters:
            query_parts.append(f"关于角色: {', '.join(involved_characters)}")
        query_parts.append(f"项目 ID: {project_id}, 第 {chapter_number} 章的背景和重要事件")
        
        query = "\n".join(query_parts)
        try:
            memory = await self._ensure_memory()
            results = await memory.search(
                query, user_id=project_id, filters={"provenance_schema": 2}, limit=100, rerank=False,
            )
            # AsyncMemory.search 返回 {"results": [...]} 格式
            result_list = results.get("results", []) if isinstance(results, dict) else results
            result_list = await filter_mem0_results(self.db, result_list or [], project_id, chapter_number)
            if result_list:
                for res in result_list:
                    mem_text = res.get('memory', '')
                    if mem_text:
                        lines.append(f"- {mem_text}")
            else:
                lines.append("（暂无相关的长期核心记忆）")
        except Exception as e:
            logger.error(f"从 mem0 检索记忆失败: {e}")
            lines.append("（检索长期核心记忆失败）")
        lines.append("")
        
        return "\n".join(lines) if len(lines) > 1 else "（无记忆层上下文）"

    async def _extract_mem0_facts(
        self, chapter_content: str, user_id: int
    ) -> List[str]:
        """从章节内容中提取核心事实（用于存入 mem0 长期记忆池）。"""
        mem0_prompt = f"""分析以下小说章节内容，提取重要的人物状态变化、关键情节转折、获得的物品信息、时间和地点的变化。

[章节内容]
{chapter_content[:8000]}

请以 JSON 格式输出将被作为长期记忆存入数据库的精简事实性句子列表：
```json
{{
  "facts": [
    "角色 A 在第 X 章获得了神秘卷轴",
    "角色 B 的左臂在与 C 的战斗中受了重伤",
    "故事的主线目标变为了寻找遗失的神器"
  ]
}}
```
提取的事实必须是绝对准确的、简练的陈述句。"""

        response = await self.llm_service.get_llm_response(
            system_prompt="你是一个专业的小说剧情记忆提取助手。请严格按照 JSON 格式输出。",
            conversation_history=[{"role": "user", "content": mem0_prompt}],
            temperature=0.2,
            user_id=user_id,
            timeout=120.0
        )

        result = parse_llm_json(response, default=None)
        if isinstance(result, dict):
            return result.get("facts", [])
        return []

    async def update_state_after_chapter(
        self,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        character_names: List[str],
        user_id: int,
        source_ref: Any = None,
    ) -> Dict[str, Any]:
        """轻量状态记忆更新：仅抽取并落库状态类记忆（CharacterState/TimelineEvent），不碰 mem0。

        standard 档（enable_state_tracking）走此入口；premium 完整记忆路径
        （update_memory_after_chapter）内部复用本方法，避免逻辑复制。
        各步骤独立错误隔离，全程降级。
        """
        results = {
            "character_states_updated": 0,
            "timeline_events_added": 0,
            "causal_chains_added": 0,
        }
        self._source_ref = source_ref
        await require_current_source(self.db, source_ref, lock=False)

        # ---- 顺序执行 2 个 LLM 提取（共享同一 async session，不可并发） ----
        character_states: Any = []
        events: Any = []

        try:
            character_states = await self._extraction_checkpoint(
                "character_states", lambda: self.extract_character_states_from_chapter(
                    project_id, chapter_number, chapter_content, character_names, user_id,
                ),
            )
        except Exception as e:
            logger.warning(f"提取角色状态失败: {e}")
            if source_ref is not None:
                raise

        try:
            events = await self._extraction_checkpoint(
                "timeline", lambda: self.extract_timeline_events_from_chapter(
                    project_id, chapter_number, chapter_content, user_id,
                ),
            )
        except Exception as e:
            logger.warning(f"提取时间线事件失败: {e}")
            if source_ref is not None:
                raise

        # ---- 步骤 1: 写入角色状态（独立错误隔离） ----
        await require_current_source(self.db, source_ref)
        try:
            for state_data in character_states:
                state_data = dict(state_data)
                char_name = state_data.pop("character_name", None)
                if char_name:
                    await self.update_character_state(
                        project_id, char_name, chapter_number, state_data
                    )
                    results["character_states_updated"] += 1
        except Exception as e:
            logger.warning(f"写入角色状态到数据库失败: {e}")
            if source_ref is not None:
                raise
            # 失败的 flush 会让 session 停在待回滚态，不复位则"独立错误隔离"名存实亡：
            # 步骤 2 必然连带报 PendingRollbackError（线上实测角色状态与时间线总是同时丢）。
            await self._safe_rollback()

        # ---- 步骤 2: 写入时间线事件（独立错误隔离） ----
        try:
            for event_data in events:
                await self.add_timeline_event(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    **event_data
                )
                results["timeline_events_added"] += 1
        except Exception as e:
            logger.warning(f"写入时间线事件到数据库失败: {e}")
            if source_ref is not None:
                raise
            await self._safe_rollback()

        return results

    async def update_memory_after_chapter(
        self,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        character_names: List[str],
        user_id: int,
        source_ref: Any = None,
    ) -> Dict[str, Any]:
        """章节完成后更新完整记忆层：状态类抽取落库（复用 update_state_after_chapter）
        + 提取新事实存入 mem0。每个步骤独立错误隔离。
        """
        results = {
            "character_states_updated": 0,
            "timeline_events_added": 0,
            "causal_chains_added": 0,
            "mem0_memories_added": 0
        }
        self._source_ref = source_ref
        await require_current_source(self.db, source_ref, lock=False)

        # ---- 状态类抽取落库（CharacterState/TimelineEvent，内部已独立错误隔离） ----
        try:
            state_results = await self.update_state_after_chapter(
                project_id, chapter_number, chapter_content, character_names, user_id, source_ref=source_ref,
            )
            results.update(state_results)
        except Exception as e:
            logger.warning(f"状态类记忆更新失败: {e}")
            if source_ref is not None:
                raise

        # ---- mem0 事实提取（独立错误隔离） ----
        facts: Any = []
        try:
            facts = await self._extraction_checkpoint(
                "mem0_facts", lambda: self._extract_mem0_facts(chapter_content, user_id),
            )
        except Exception as e:
            logger.warning(f"提取 mem0 事实失败: {e}")
            if source_ref is not None:
                raise
            facts = []

        # ---- 存入 mem0 长期记忆（独立错误隔离） ----

        try:
            if facts:
                messages = [{"role": "user", "content": fact} for fact in facts]
                memory = await self._ensure_memory()
                # No inference/merging in the external cache: SQL owns canon.
                await require_current_source(self.db, source_ref)
                raw = source_payload(source_ref)
                if raw and raw.get("source_derivation_id"):
                    added = await memory.add(
                        messages, user_id=project_id, infer=False,
                        metadata={**raw, "provenance_schema": 2},
                    )
                    import hashlib
                    entries = added.get("results", []) if isinstance(added, dict) else added
                    results["memory_ids"] = [str(e["id"]) for e in entries or [] if e.get("id")]
                    results["memory_hashes"] = {
                        str(e["id"]): hashlib.sha256((e.get("memory") or "").encode()).hexdigest()
                        for e in entries or [] if e.get("id")
                    }
                    if len(results["memory_ids"]) != len(messages) or len(results["memory_hashes"]) != len(messages):
                        raise RuntimeError("Mem0 未确认完整写入，不能发布成功收据")
                    results["mem0_memories_added"] = len(results["memory_ids"])
        except Exception as e:
            logger.warning(f"存入 mem0 记忆失败: {e}")
            if source_ref is not None:
                raise

        logger.info(
            f"项目 {project_id} 第 {chapter_number} 章记忆层更新完成: "
            f"角色状态 {results['character_states_updated']}, "
            f"时间线事件 {results['timeline_events_added']}, "
            f"长期记忆(mem0) {results['mem0_memories_added']}"
        )

        return results

    async def check_consistency(
        self,
        project_id: str,
        chapter_number: int,
        chapter_content: str,
        user_id: int
    ) -> Dict[str, Any]:
        """检查章节与记忆层的一致性"""
        issues = []
        
        # 获取记忆层上下文
        memory_context = await self.get_memory_context(project_id, chapter_number)
        
        prompt = f"""检查以下章节内容与记忆层上下文的一致性。

[记忆层上下文]
{memory_context}

[章节内容]
{chapter_content[:6000]}

请检查以下方面的一致性：
1. 角色位置是否合理（不能瞬移）
2. 角色情绪是否连贯
3. 角色持有物品是否正确
4. 时间流逝是否合理
5. 事件因果是否自洽

以 JSON 格式输出检查结果：
```json
{{
  "consistent": true/false,
  "issues": [
    {{
      "type": "location/emotion/inventory/time/causality",
      "severity": "critical/warning/minor",
      "description": "问题描述",
      "suggestion": "修复建议"
    }}
  ]
}}
```"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt="你是一个专业的小说一致性检查助手。请严格按照 JSON 格式输出。",
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.2,
                user_id=user_id,
                timeout=120.0
            )
            
            result = parse_llm_json(response, default=None)
            if isinstance(result, dict):
                return result
        except Exception as e:
            logger.warning(f"一致性检查失败: {e}")
        
        return {"consistent": True, "issues": []}
