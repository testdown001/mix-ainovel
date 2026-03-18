# AIMETA P=时序状态聚合|R=统一查询角色状态/事件/因果链/伏笔/时间/力量/关系网|E=get_world_snapshot
"""
时序状态服务 — 统一聚合多个数据源的时序状态快照。

纯 DB 查询，不依赖 LLMService。将碎片化的时序数据（角色状态、重大事件、
因果链、伏笔紧迫度、故事时间、力量等级、角色关系）整合为一个 WorldStateSnapshot，
再转换为 EvidenceItem 列表供证据路由使用。
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class WorldStateSnapshot:
    """时序状态快照，聚合多个数据源。"""

    characters: List[Dict[str, Any]] = field(default_factory=list)
    recent_events: List[Dict[str, Any]] = field(default_factory=list)
    pending_chains: List[Dict[str, Any]] = field(default_factory=list)
    foreshadowing_alerts: Dict[str, List[Dict[str, Any]]] = field(
        default_factory=lambda: {"urgent": [], "due_soon": [], "overdue": []}
    )
    story_time: Dict[str, Any] = field(default_factory=dict)
    power_landscape: List[Dict[str, Any]] = field(default_factory=list)
    relationship_network: str = ""


class TemporalStateService:
    """统一时序状态聚合，纯 DB 查询，目标 <200ms。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_world_snapshot(
        self,
        project_id: str,
        chapter_number: int,
        *,
        involved_characters: Optional[List[str]] = None,
        blueprint_dict: Optional[Dict[str, Any]] = None,
        include_foreshadowing: bool = True,
    ) -> WorldStateSnapshot:
        """并行查询 5 个数据源，聚合为 WorldStateSnapshot。"""
        snapshot = WorldStateSnapshot()

        tasks = [
            self._fetch_characters(project_id, chapter_number, involved_characters, snapshot),
            self._fetch_events(project_id, chapter_number, snapshot),
            self._fetch_causal_chains(project_id, snapshot),
            self._fetch_story_time(project_id, snapshot),
        ]
        if include_foreshadowing:
            tasks.append(self._fetch_foreshadowing(project_id, chapter_number, snapshot))

        await asyncio.gather(*tasks, return_exceptions=True)

        # 关系网从 blueprint_dict 同步构建（无 DB 查询）
        if blueprint_dict:
            self._build_relationship_network(blueprint_dict, snapshot)

        return snapshot

    # ------------------------------------------------------------------ #
    #  数据源抓取（每个方法独立 try/except 保证单源异常不阻塞整体）
    # ------------------------------------------------------------------ #

    async def _fetch_characters(
        self,
        project_id: str,
        chapter_number: int,
        involved_characters: Optional[List[str]],
        snapshot: WorldStateSnapshot,
    ) -> None:
        try:
            from .memory_layer_service import MemoryLayerService

            mem = MemoryLayerService(db=self.db)

            states = await mem.get_all_character_states(project_id, chapter_number)

            for s in states:
                char_dict: Dict[str, Any] = {
                    "name": s.character_name,
                    "location": s.location,
                    "emotion": s.emotion,
                    "health_status": s.health_status,
                    "power_level": s.power_level,
                    "current_goals": s.current_goals,
                }
                snapshot.characters.append(char_dict)
                if s.power_level:
                    snapshot.power_landscape.append(
                        {"name": s.character_name, "power_level": s.power_level}
                    )

            # 过滤：involved_characters 优先
            if involved_characters:
                involved_set = set(involved_characters)
                primary = [c for c in snapshot.characters if c["name"] in involved_set]
                secondary = [c for c in snapshot.characters if c["name"] not in involved_set]
                snapshot.characters = primary + secondary[:3]
        except Exception:
            logger.warning("时序状态: 角色状态查询异常", exc_info=True)

    async def _fetch_events(
        self,
        project_id: str,
        chapter_number: int,
        snapshot: WorldStateSnapshot,
    ) -> None:
        try:
            from .memory_layer_service import MemoryLayerService

            mem = MemoryLayerService(db=self.db)

            start_ch = max(1, chapter_number - 3)
            events = await mem.get_timeline(project_id, start_chapter=start_ch, end_chapter=chapter_number - 1)
            for ev in events:
                if hasattr(ev, "importance") and ev.importance is not None and ev.importance < 7:
                    continue
                snapshot.recent_events.append({
                    "chapter": ev.chapter_number,
                    "event": ev.event_description if hasattr(ev, "event_description") else str(ev),
                    "importance": getattr(ev, "importance", None),
                })
        except Exception:
            logger.warning("时序状态: 事件查询异常", exc_info=True)

    async def _fetch_causal_chains(
        self,
        project_id: str,
        snapshot: WorldStateSnapshot,
    ) -> None:
        try:
            from .memory_layer_service import MemoryLayerService

            mem = MemoryLayerService(db=self.db)

            chains = await mem.get_pending_causal_chains(project_id)
            for c in chains:
                snapshot.pending_chains.append({
                    "cause": getattr(c, "cause_description", str(c)),
                    "cause_chapter": getattr(c, "cause_chapter", None),
                    "expected_effect": getattr(c, "expected_effect", None),
                })
        except Exception:
            logger.warning("时序状态: 因果链查询异常", exc_info=True)

    async def _fetch_story_time(
        self,
        project_id: str,
        snapshot: WorldStateSnapshot,
    ) -> None:
        try:
            from .memory_layer_service import MemoryLayerService

            mem = MemoryLayerService(db=self.db)

            tracker = await mem.get_or_create_time_tracker(project_id)
            snapshot.story_time = {
                "chapter_time_map": getattr(tracker, "chapter_time_map", {}),
            }
        except Exception:
            logger.warning("时序状态: 故事时间查询异常", exc_info=True)

    async def _fetch_foreshadowing(
        self,
        project_id: str,
        chapter_number: int,
        snapshot: WorldStateSnapshot,
    ) -> None:
        try:
            from .foreshadowing_tracker_service import ForeshadowingTrackerService

            fs = ForeshadowingTrackerService(db=self.db)

            alerts = await fs.get_foreshadowings_for_chapter(project_id, chapter_number)
            for category in ("urgent", "due_soon", "overdue"):
                items = alerts.get(category, [])
                snapshot.foreshadowing_alerts[category] = [
                    {
                        "name": getattr(f, "name", str(f)),
                        "description": getattr(f, "description", ""),
                        "urgency": getattr(f, "urgency", None),
                        "target_chapter": getattr(f, "target_reveal_chapter", None),
                    }
                    for f in items
                ]
        except Exception:
            logger.warning("时序状态: 伏笔查询异常", exc_info=True)

    def _build_relationship_network(
        self,
        blueprint_dict: Dict[str, Any],
        snapshot: WorldStateSnapshot,
    ) -> None:
        rels = blueprint_dict.get("relationships", []) or []
        if not rels:
            return
        lines: List[str] = []
        for rel in rels[:20]:
            from_name = rel.get("from_name") or rel.get("source_name", "?")
            to_name = rel.get("to_name") or rel.get("target_name", "?")
            rel_type = rel.get("relationship_type", "")
            desc = (rel.get("description", "") or "")[:60]
            lines.append(f"- {from_name} <-> {to_name}: {rel_type} ({desc})")
        snapshot.relationship_network = "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  转换为 EvidenceItem 列表
    # ------------------------------------------------------------------ #

    def to_evidence_items(
        self,
        snapshot: WorldStateSnapshot,
        budget_tokens: int = 1500,
    ) -> list:
        """按优先级将快照转换为 EvidenceItem 列表。

        优先级：紧迫伏笔(0.80) > 关系网(0.75) > 因果链(0.70)
                > 角色状态(0.65) = 力量(0.65) > 事件(0.60)
        """
        from .context_planner_service import EvidenceItem

        items: list = []
        token_estimate = 0

        def _add(title: str, content: str, score: float) -> bool:
            nonlocal token_estimate
            # 粗估 1 token ≈ 2 中文字符
            est = len(content)
            if token_estimate + est > budget_tokens * 2:
                return False
            items.append(EvidenceItem(
                source="state_rag",
                title=title,
                content=content,
                score=score,
                metadata={"origin": "temporal_snapshot"},
            ))
            token_estimate += est
            return True

        # 1. 紧迫伏笔 (0.80)
        for category, label in [("urgent", "紧急"), ("overdue", "逾期"), ("due_soon", "临近")]:
            for f in snapshot.foreshadowing_alerts.get(category, []):
                text = f"[{label}伏笔] {f.get('name', '')}: {f.get('description', '')}"
                if not _add(f"伏笔-{label}", text, 0.80):
                    break

        # 2. 关系网 (0.75)
        if snapshot.relationship_network:
            _add("角色关系网", snapshot.relationship_network, 0.75)

        # 3. 因果链 (0.70)
        for c in snapshot.pending_chains[:5]:
            text = f"[待解因果] 第{c.get('cause_chapter', '?')}章: {c.get('cause', '')} → {c.get('expected_effect', '?')}"
            if not _add("因果链", text, 0.70):
                break

        # 4. 角色状态 (0.65)
        for ch in snapshot.characters[:6]:
            parts = []
            if ch.get("location"):
                parts.append(f"位于{ch['location']}")
            if ch.get("emotion"):
                parts.append(f"情绪{ch['emotion']}")
            if ch.get("health_status") and ch["health_status"] not in ("healthy", "正常"):
                parts.append(f"状态{ch['health_status']}")
            if ch.get("power_level"):
                parts.append(f"实力{ch['power_level']}")
            if parts:
                text = f"{ch['name']}：{'，'.join(parts)}"
                if not _add(f"角色-{ch['name']}", text, 0.65):
                    break

        # 5. 重大事件 (0.60)
        for ev in snapshot.recent_events[:5]:
            text = f"第{ev.get('chapter', '?')}章: {ev.get('event', '')}"
            if not _add("重大事件", text, 0.60):
                break

        return items
