from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class RetrievalTask:
    task_id: str
    source: str
    mode: str
    query_template: str
    priority: int = 1
    max_items: int = 5
    filters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "RetrievalTask":
        payload = dict(data or {})
        return cls(
            task_id=str(payload.get("task_id") or ""),
            source=str(payload.get("source") or ""),
            mode=str(payload.get("mode") or ""),
            query_template=str(payload.get("query_template") or ""),
            priority=int(payload.get("priority") or 1),
            max_items=int(payload.get("max_items") or 5),
            filters=dict(payload.get("filters") or {}),
        )


@dataclass
class SkillPolicy:
    skill_id: str
    phase: str
    params: Dict[str, Any] = field(default_factory=dict)
    retrieval_hints: List[str] = field(default_factory=list)
    prompt_hints: List[str] = field(default_factory=list)
    verify_hints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "SkillPolicy":
        payload = dict(data or {})
        return cls(
            skill_id=str(payload.get("skill_id") or ""),
            phase=str(payload.get("phase") or "pre_prompt"),
            params=dict(payload.get("params") or {}),
            retrieval_hints=[str(item) for item in (payload.get("retrieval_hints") or []) if item],
            prompt_hints=[str(item) for item in (payload.get("prompt_hints") or []) if item],
            verify_hints=[str(item) for item in (payload.get("verify_hints") or []) if item],
        )


@dataclass
class ScenePlanNode:
    scene_id: str
    goal: str
    target_words: int
    dependencies: List[str] = field(default_factory=list)
    required_evidence: List[str] = field(default_factory=list)
    conflict: str = ""
    characters: List[str] = field(default_factory=list)
    verification_hints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ScenePlanNode":
        payload = dict(data or {})
        return cls(
            scene_id=str(payload.get("scene_id") or payload.get("scene") or ""),
            goal=str(payload.get("goal") or "推进剧情"),
            target_words=int(payload.get("target_words") or 700),
            dependencies=[str(item) for item in (payload.get("dependencies") or []) if item],
            required_evidence=[str(item) for item in (payload.get("required_evidence") or []) if item],
            conflict=str(payload.get("conflict") or ""),
            characters=[str(item) for item in (payload.get("characters") or []) if item],
            verification_hints=[str(item) for item in (payload.get("verification_hints") or []) if item],
        )


@dataclass
class ContextStrategy:
    mode: str
    reason: str
    query_limit: int
    required_sources: List[str] = field(default_factory=list)
    long_context_modules: List[str] = field(default_factory=list)
    rag_focus: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ContextStrategy":
        payload = dict(data or {})
        return cls(
            mode=str(payload.get("mode") or "rag"),
            reason=str(payload.get("reason") or "default"),
            query_limit=int(payload.get("query_limit") or 4),
            required_sources=[str(item) for item in (payload.get("required_sources") or []) if item],
            long_context_modules=[str(item) for item in (payload.get("long_context_modules") or []) if item],
            rag_focus=[str(item) for item in (payload.get("rag_focus") or []) if item],
        )


@dataclass
class ContextPlan:
    intent: Dict[str, Any]
    chapter_phase: str
    retrieval_tasks: List[RetrievalTask]
    skill_policies: List[SkillPolicy]
    prompt_modules: List[str]
    verification_tasks: List[str]
    budgets: Dict[str, Any] = field(default_factory=dict)
    is_fast_path: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    scene_plan: List[ScenePlanNode] = field(default_factory=list)
    context_strategy: Optional[ContextStrategy] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": dict(self.intent),
            "chapter_phase": self.chapter_phase,
            "retrieval_tasks": [item.to_dict() for item in self.retrieval_tasks],
            "skill_policies": [item.to_dict() for item in self.skill_policies],
            "prompt_modules": list(self.prompt_modules),
            "verification_tasks": list(self.verification_tasks),
            "budgets": dict(self.budgets),
            "is_fast_path": self.is_fast_path,
            "metadata": dict(self.metadata),
            "scene_plan": [item.to_dict() for item in self.scene_plan],
            "context_strategy": self.context_strategy.to_dict() if self.context_strategy else None,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ContextPlan":
        payload = dict(data or {})
        return cls(
            intent=dict(payload.get("intent") or {}),
            chapter_phase=str(payload.get("chapter_phase") or "development"),
            retrieval_tasks=[
                RetrievalTask.from_dict(item)
                for item in (payload.get("retrieval_tasks") or [])
                if item
            ],
            skill_policies=[
                SkillPolicy.from_dict(item)
                for item in (payload.get("skill_policies") or [])
                if item
            ],
            prompt_modules=[str(item) for item in (payload.get("prompt_modules") or []) if item],
            verification_tasks=[str(item) for item in (payload.get("verification_tasks") or []) if item],
            budgets=dict(payload.get("budgets") or {}),
            is_fast_path=bool(payload.get("is_fast_path")),
            metadata=dict(payload.get("metadata") or {}),
            scene_plan=[
                ScenePlanNode.from_dict(item)
                for item in (payload.get("scene_plan") or [])
                if item
            ],
            context_strategy=ContextStrategy.from_dict(payload.get("context_strategy"))
            if payload.get("context_strategy")
            else None,
        )


@dataclass
class EvidenceItem:
    source: str
    title: str
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationEvidencePack:
    local_plot: List[EvidenceItem] = field(default_factory=list)
    global_arc: List[EvidenceItem] = field(default_factory=list)
    state_items: List[EvidenceItem] = field(default_factory=list)
    symbolic_items: List[EvidenceItem] = field(default_factory=list)
    graded_summary: Dict[str, Any] = field(default_factory=dict)


class ContextPlannerService:
    """构建章节生成前的统一 ContextPlan。"""

    _PHASE_KEYWORDS: Dict[str, Sequence[str]] = {
        "resolution": ("收束", "落幕", "终局", "尾声", "回收", "结局"),
        "climax": ("决战", "高潮", "爆发", "逆转", "大战", "摊牌"),
        "setup": ("开端", "初入", "起步", "启程", "新手", "序章"),
    }

    _SKILL_HINTS: Dict[str, Dict[str, Any]] = {
        "dialogue_polish": {
            "phase": "pre_prompt",
            "retrieval_hints": ["角色对白样本", "声纹一致性"],
            "prompt_hints": ["角色口头禅", "对白节奏稳定性"],
            "verify_hints": ["对白风格漂移检查"],
        },
        "foreshadowing": {
            "phase": "retrieve",
            "retrieval_hints": ["未回收伏笔", "相关章节片段"],
            "prompt_hints": ["本章伏笔处理清单"],
            "verify_hints": ["伏笔埋设/强化/回收状态"],
        },
        "rhythm_control": {
            "phase": "pre_plan",
            "retrieval_hints": ["近5章节奏分布", "爽点密度"],
            "prompt_hints": ["节奏配额", "场景推进速度"],
            "verify_hints": ["节奏目标达成度"],
        },
        "consistency_check": {
            "phase": "verify",
            "retrieval_hints": ["角色状态", "时间线", "硬性设定边界"],
            "prompt_hints": ["设定冲突警戒"],
            "verify_hints": ["一致性冲突扫描"],
        },
    }

    async def build_plan(
        self,
        *,
        project_id: str,
        chapter_number: int,
        writing_notes: str,
        flow_config: Dict[str, Any],
        selected_skills: Optional[List[Dict[str, Any]]] = None,
        skill_policies: Optional[Sequence[Dict[str, Any] | SkillPolicy]] = None,
        user_id: int = 0,
        blueprint: Optional[Dict[str, Any]] = None,
        outline_data: Optional[Dict[str, Any]] = None,
        history_context: Optional[Dict[str, Any]] = None,
    ) -> ContextPlan:
        blueprint_data = blueprint or {}
        outline = outline_data or {}
        history = history_context or {}
        skill_items = selected_skills if selected_skills is not None else list(flow_config.get("selected_skills") or [])
        total_outlines = len(blueprint_data.get("chapter_outline") or [])
        chapter_phase, phase_reason = self._infer_chapter_phase(
            chapter_number=chapter_number,
            total_chapters=total_outlines,
            outline_title=str(outline.get("title") or ""),
            outline_summary=str(outline.get("summary") or ""),
        )
        is_fast_path = bool(flow_config.get("enable_fast_path")) or str(flow_config.get("preset") or "") == "fast"
        resolved_skill_policies = self._normalize_skill_policies(skill_policies)
        if not resolved_skill_policies:
            resolved_skill_policies = self._build_skill_policies(skill_items)
        retrieval_tasks = self._build_retrieval_tasks(
            chapter_number=chapter_number,
            chapter_phase=chapter_phase,
            total_outlines=total_outlines,
            flow_config=flow_config,
            history_context=history,
            skill_policies=resolved_skill_policies,
            is_fast_path=is_fast_path,
        )
        context_strategy = self._build_context_strategy(
            chapter_number=chapter_number,
            chapter_phase=chapter_phase,
            flow_config=flow_config,
            history_context=history,
            retrieval_tasks=retrieval_tasks,
            is_fast_path=is_fast_path,
        )
        self._apply_context_strategy(retrieval_tasks, context_strategy)
        prompt_modules = self._build_prompt_modules(
            flow_config=flow_config,
            history_context=history,
            skill_policies=resolved_skill_policies,
            is_fast_path=is_fast_path,
        )
        verification_tasks = self._build_verification_tasks(
            flow_config=flow_config,
            skill_policies=resolved_skill_policies,
            is_fast_path=is_fast_path,
        )
        character_names = [
            str(item.get("name"))
            for item in (blueprint_data.get("characters") or [])
            if isinstance(item, dict) and item.get("name")
        ]
        intent = {
            "project_id": project_id,
            "chapter_number": chapter_number,
            "chapter_title": str(outline.get("title") or f"第{chapter_number}章"),
            "chapter_summary": str(outline.get("summary") or ""),
            "writing_notes": writing_notes or "",
            "core_goal": str(outline.get("summary") or outline.get("title") or "").strip(),
            "continuity_anchor": str(history.get("previous_summary") or ""),
            "character_focus": character_names[:6],
            "suspense_target": "high" if chapter_phase in {"climax", "resolution"} else "medium",
        }
        budgets = self._build_budgets(
            retrieval_tasks=retrieval_tasks,
            prompt_modules=prompt_modules,
            verification_tasks=verification_tasks,
            is_fast_path=is_fast_path,
        )
        scene_plan = self._build_scene_plan(
            chapter_phase=chapter_phase,
            outline_title=str(outline.get("title") or f"第{chapter_number}章"),
            outline_summary=str(outline.get("summary") or ""),
            writing_notes=writing_notes or "",
            character_names=character_names,
            target_words=self._safe_int(flow_config.get("target_word_count") or flow_config.get("word_count"), 3500),
            skill_policies=resolved_skill_policies,
            context_strategy=context_strategy,
        )
        metadata = {
            "plan_version": "v0.1",
            "source": "context_planner_service",
            "preset": str(flow_config.get("preset") or "fast"),
            "user_id": user_id,
            "phase_reason": phase_reason,
            "total_outlines": total_outlines,
            "completed_chapters": len(history.get("completed_chapters") or []),
            "retrieval_mode": str(flow_config.get("rag_retrieval_mode") or "vector"),
        }
        return ContextPlan(
            intent=intent,
            chapter_phase=chapter_phase,
            retrieval_tasks=retrieval_tasks,
            skill_policies=resolved_skill_policies,
            prompt_modules=prompt_modules,
            verification_tasks=verification_tasks,
            budgets=budgets,
            is_fast_path=is_fast_path,
            metadata=metadata,
            scene_plan=scene_plan,
            context_strategy=context_strategy,
        )

    def build_retrieval_queries(
        self,
        *,
        plan: ContextPlan,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        character_names: Optional[List[str]] = None,
        story_skeleton: Optional[str] = None,
        fast_rag_queries: Optional[List[str]] = None,
    ) -> List[str]:
        if plan.is_fast_path and fast_rag_queries:
            return self._dedupe_queries([str(item).strip() for item in fast_rag_queries if item], limit=4)

        queries: List[str] = []
        names = [str(item).strip() for item in (character_names or []) if item]
        for task in sorted(plan.retrieval_tasks, key=lambda item: (-item.priority, item.task_id)):
            if task.source == "local_plot_rag":
                self._append_query(queries, outline_title)
                self._append_query(queries, outline_summary)
                if writing_notes and writing_notes != "无额外写作指令":
                    self._append_query(queries, writing_notes)
            elif task.source == "global_arc_rag" and story_skeleton:
                self._append_query(queries, story_skeleton[:200])
            elif task.source == "state_rag" and names:
                self._append_query(queries, " ".join(names[:6]))
            elif task.source == "symbolic_rag":
                self._append_query(queries, f"{outline_title}\n{outline_summary}".strip())

        if not queries:
            self._append_query(queries, outline_title)
            self._append_query(queries, outline_summary)

        query_limit = plan.context_strategy.query_limit if plan.context_strategy else 4
        return self._dedupe_queries(queries, limit=query_limit)

    def _build_skill_policies(self, selected_skills: Sequence[Dict[str, Any]]) -> List[SkillPolicy]:
        policies: List[SkillPolicy] = []
        for item in selected_skills:
            if not isinstance(item, dict):
                continue
            skill_id = str(item.get("skill_id") or "").strip()
            if not skill_id:
                continue
            hint_config = self._SKILL_HINTS.get(skill_id, {})
            params = item.get("params") if isinstance(item.get("params"), dict) else {}
            policies.append(
                SkillPolicy(
                    skill_id=skill_id,
                    phase=str(hint_config.get("phase") or "pre_prompt"),
                    params=params,
                    retrieval_hints=list(hint_config.get("retrieval_hints") or []),
                    prompt_hints=list(hint_config.get("prompt_hints") or []),
                    verify_hints=list(hint_config.get("verify_hints") or []),
                )
            )
        return policies

    def _normalize_skill_policies(
        self,
        skill_policies: Optional[Sequence[Dict[str, Any] | SkillPolicy]],
    ) -> List[SkillPolicy]:
        resolved: List[SkillPolicy] = []
        for item in skill_policies or []:
            if isinstance(item, SkillPolicy):
                resolved.append(item)
            elif isinstance(item, dict):
                policy = SkillPolicy.from_dict(item)
                if policy.skill_id:
                    resolved.append(policy)
        return resolved

    def _build_retrieval_tasks(
        self,
        *,
        chapter_number: int,
        chapter_phase: str,
        total_outlines: int,
        flow_config: Dict[str, Any],
        history_context: Dict[str, Any],
        skill_policies: Sequence[SkillPolicy],
        is_fast_path: bool,
    ) -> List[RetrievalTask]:
        if not flow_config.get("enable_rag", True):
            return []

        tasks: List[RetrievalTask] = [
            RetrievalTask(
                task_id="local_plot",
                source="local_plot_rag",
                mode="vector",
                query_template="{outline_title}\n{outline_summary}",
                priority=3,
                max_items=4 if is_fast_path else 6,
            )
        ]

        has_story_skeleton = bool(history_context.get("story_skeleton"))
        if not is_fast_path and (has_story_skeleton or total_outlines >= 10):
            tasks.append(
                RetrievalTask(
                    task_id="global_arc",
                    source="global_arc_rag",
                    mode="summary",
                    query_template="{story_skeleton}\n{outline_summary}",
                    priority=2,
                    max_items=3,
                )
            )

        if flow_config.get("enable_memory") or flow_config.get("enable_character_relationships") or chapter_number > 1:
            state_mode = "temporal_snapshot" if flow_config.get("enable_temporal_state") else "structured"
            tasks.append(
                RetrievalTask(
                    task_id="state_snapshot",
                    source="state_rag",
                    mode=state_mode,
                    query_template="{character_names}\n{writing_notes}",
                    priority=2,
                    max_items=4 if is_fast_path else 6,
                )
            )

        if (
            flow_config.get("enable_foreshadowing")
            or flow_config.get("enable_constitution")
            or flow_config.get("enable_power_system")
            or flow_config.get("enable_faction")
        ):
            tasks.append(
                RetrievalTask(
                    task_id="symbolic_constraints",
                    source="symbolic_rag",
                    mode="structured",
                    query_template="{outline_title}\n{symbolic_constraints}",
                    priority=2 if chapter_phase in {"climax", "resolution"} else 1,
                    max_items=3,
                )
            )

        if not is_fast_path and chapter_number >= 4:
            tasks.append(
                RetrievalTask(
                    task_id="entropy_probe",
                    source="symbolic_rag",
                    mode="entropy",
                    query_template="{dormant_thread}",
                    priority=0,
                    max_items=1,
                    filters={"strategy": "round_robin"},
                )
            )

        if any(policy.retrieval_hints for policy in skill_policies):
            tasks[0].filters["skill_augmented"] = True

        return tasks

    def _build_context_strategy(
        self,
        *,
        chapter_number: int,
        chapter_phase: str,
        flow_config: Dict[str, Any],
        history_context: Dict[str, Any],
        retrieval_tasks: Sequence[RetrievalTask],
        is_fast_path: bool,
    ) -> ContextStrategy:
        task_sources = [task.source for task in retrieval_tasks]
        if is_fast_path:
            return ContextStrategy(
                mode="rag_minimal",
                reason="fast_path_latency_budget",
                query_limit=4,
                required_sources=[source for source in task_sources if source in {"local_plot_rag", "state_rag"}],
                rag_focus=["local_plot", "recent_state"],
            )

        has_long_context = bool(history_context.get("previous_summary") or history_context.get("story_skeleton"))
        needs_symbolic = any(
            flow_config.get(key)
            for key in ("enable_foreshadowing", "enable_power_system", "enable_faction", "enable_constitution")
        )
        if chapter_phase in {"climax", "resolution"} or needs_symbolic:
            return ContextStrategy(
                mode="hybrid",
                reason="high_dependency_chapter_requires_rag_and_long_context",
                query_limit=6,
                required_sources=task_sources,
                long_context_modules=["previous_summary", "previous_tail", "story_skeleton"],
                rag_focus=["local_plot", "state_snapshot", "symbolic_constraints"],
            )
        if chapter_number <= 2 and has_long_context:
            return ContextStrategy(
                mode="long_context_first",
                reason="early_chapter_continuity_prefers_contiguous_context",
                query_limit=2,
                required_sources=[source for source in task_sources if source != "symbolic_rag"],
                long_context_modules=["previous_summary", "previous_tail", "story_skeleton"],
                rag_focus=["local_plot"],
            )
        return ContextStrategy(
            mode="rag_balanced",
            reason="default_balanced_retrieval",
            query_limit=4,
            required_sources=task_sources,
            long_context_modules=["previous_summary", "previous_tail"],
            rag_focus=["local_plot", "state_snapshot"],
        )

    @staticmethod
    def _apply_context_strategy(
        retrieval_tasks: List[RetrievalTask],
        context_strategy: ContextStrategy,
    ) -> None:
        for task in retrieval_tasks:
            task.filters["context_strategy"] = context_strategy.mode
            if context_strategy.mode == "hybrid" and task.source in {"symbolic_rag", "state_rag"}:
                task.priority += 1
                task.max_items = max(task.max_items, 5)
            elif context_strategy.mode == "long_context_first" and task.source == "local_plot_rag":
                task.max_items = min(task.max_items, 3)

    def _build_scene_plan(
        self,
        *,
        chapter_phase: str,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        character_names: Sequence[str],
        target_words: int,
        skill_policies: Sequence[SkillPolicy],
        context_strategy: ContextStrategy,
    ) -> List[ScenePlanNode]:
        total = target_words if target_words > 0 else 3500
        characters = list(character_names[:4])
        skill_verify_hints = [
            hint
            for policy in skill_policies
            for hint in policy.verify_hints
        ]
        if chapter_phase in {"climax", "resolution"}:
            goals = [
                ("scene_1", f"承接《{outline_title}》开局，明确旧线索和当前危机", 0.25, []),
                ("scene_2", outline_summary or writing_notes or "推进核心冲突并制造选择压力", 0.45, ["scene_1"]),
                ("scene_3", "回收关键情绪/伏笔并留下追更钩子", 0.30, ["scene_2"]),
            ]
        elif chapter_phase == "setup":
            goals = [
                ("scene_1", f"建立《{outline_title}》的处境、人物欲望和读者问题", 0.35, []),
                ("scene_2", outline_summary or "引入第一处阻力或诱因", 0.40, ["scene_1"]),
                ("scene_3", "用具体动作触发下一章期待", 0.25, ["scene_2"]),
            ]
        else:
            goals = [
                ("scene_1", f"承接上一章，进入《{outline_title}》的行动场", 0.28, []),
                ("scene_2", outline_summary or writing_notes or "推进人物冲突和信息增量", 0.44, ["scene_1"]),
                ("scene_3", "完成本章转折并压出新的问题", 0.28, ["scene_2"]),
            ]
        return [
            ScenePlanNode(
                scene_id=scene_id,
                goal=goal,
                target_words=max(300, int(total * ratio)),
                dependencies=dependencies,
                required_evidence=list(context_strategy.required_sources),
                conflict="人物目标与外部阻力正面碰撞" if index == 2 else "",
                characters=characters,
                verification_hints=skill_verify_hints,
            )
            for index, (scene_id, goal, ratio, dependencies) in enumerate(goals, start=1)
        ]

    def _build_prompt_modules(
        self,
        *,
        flow_config: Dict[str, Any],
        history_context: Dict[str, Any],
        skill_policies: Sequence[SkillPolicy],
        is_fast_path: bool,
    ) -> List[str]:
        modules = ["chapter_goal", "word_count_rule", "world_blueprint"]
        if flow_config.get("enable_mission_brief"):
            modules.append("mission_brief")
        else:
            modules.append("mission_json")

        modules.extend(["previous_summary", "previous_tail", "hard_constraints"])

        if history_context.get("story_skeleton") and not is_fast_path:
            modules.append("story_skeleton")
        if flow_config.get("enable_rag", True):
            modules.append("rag_local")
            if not is_fast_path:
                modules.append("rag_global")
        # [项目长期记忆] 数据是无条件预取的：非 fast 路径一律注入（不再依赖 enable_memory）；
        # enable_memory 继续独占管 [记忆层上下文]/[角色当前状态]（character_state 模块）。
        if flow_config.get("enable_memory") or not is_fast_path:
            modules.append("project_memory")
        if flow_config.get("enable_memory"):
            modules.append("character_state")
        if not is_fast_path:
            # 卷级前情 + 全书脉络：分层长程记忆转正注入（fast 保持轻量不注入）
            modules.append("long_range_memory")
        if flow_config.get("enable_foreshadowing"):
            modules.append("foreshadowing_alerts")
        if flow_config.get("enable_power_system"):
            modules.append("power_system")
        if flow_config.get("enable_character_relationships"):
            modules.append("relationship_context")
        if skill_policies:
            modules.append("skill_instructions")

        return modules

    def _build_verification_tasks(
        self,
        *,
        flow_config: Dict[str, Any],
        skill_policies: Sequence[SkillPolicy],
        is_fast_path: bool,
    ) -> List[str]:
        tasks = ["continuity_check"]
        tasks.append("claim_level_verification")
        if flow_config.get("enable_consistency"):
            tasks.append("consistency_check")
        if flow_config.get("enable_foreshadowing"):
            tasks.append("foreshadowing_check")
        if flow_config.get("enable_six_dimension"):
            tasks.append("six_dimension_review")
        if flow_config.get("enable_reader_sim"):
            tasks.append("reader_simulation")
        if flow_config.get("enable_self_critique"):
            tasks.append("self_critique")
        if not is_fast_path:
            tasks.append("commercial_hook_check")
        if any(policy.verify_hints for policy in skill_policies):
            tasks.append("skill_policy_check")
        return tasks

    def _build_budgets(
        self,
        *,
        retrieval_tasks: Sequence[RetrievalTask],
        prompt_modules: Sequence[str],
        verification_tasks: Sequence[str],
        is_fast_path: bool,
    ) -> Dict[str, Any]:
        """构建统一的 Token 预算配额，防止 Prompt 过载和成本激增。

        预算策略：
        - Fast 模式：严格限制，优先速度
        - Balanced 模式：平衡质量与成本
        - 每类检索任务都有明确的 Token 上限
        """
        max_retrieval_items = sum(item.max_items for item in retrieval_tasks)

        # Token 预算配额（字符数估算，1 token ≈ 1.5 中文字符）
        if is_fast_path:
            # Fast 模式：严格限制
            token_budgets = {
                "max_context_tokens": 8000,           # 总上下文 Token 上限
                "max_rag_tokens": 2000,               # RAG 检索内容上限
                "max_history_tokens": 1500,           # 历史章节上限
                "max_blueprint_tokens": 1000,         # 蓝图内容上限
                "max_mission_tokens": 800,            # Mission 上限
                "max_memory_tokens": 500,             # 记忆层上限
                "max_skill_tokens": 300,              # 技能指令上限
                "max_verification_tokens": 1000,      # 验证任务上限
                "per_retrieval_item_tokens": 300,     # 单个检索项上限
            }
        else:
            # Balanced 模式：平衡质量与成本
            token_budgets = {
                "max_context_tokens": 16000,          # 总上下文 Token 上限
                "max_rag_tokens": 4000,               # RAG 检索内容上限
                "max_history_tokens": 3000,           # 历史章节上限
                "max_blueprint_tokens": 2000,         # 蓝图内容上限
                "max_mission_tokens": 1500,           # Mission 上限
                "max_memory_tokens": 1000,            # 记忆层上限
                "max_skill_tokens": 600,              # 技能指令上限
                "max_verification_tokens": 2000,      # 验证任务上限
                "per_retrieval_item_tokens": 500,     # 单个检索项上限
            }

        # 检索任务预算分配
        retrieval_budgets = {}
        for task in retrieval_tasks:
            task_budget = task.max_items * token_budgets["per_retrieval_item_tokens"]
            retrieval_budgets[task.task_id] = {
                "max_items": task.max_items,
                "max_tokens": task_budget,
                "priority": task.priority,
            }

        return {
            # 基础配额
            "max_retrieval_tasks": len(retrieval_tasks),
            "max_retrieval_items": max_retrieval_items,
            "max_prompt_modules": len(prompt_modules),
            "max_verification_tasks": len(verification_tasks),
            "retrieval_retry_limit": 0 if is_fast_path else 1,
            "mode": "fast" if is_fast_path else "balanced",

            # Token 预算配额
            "token_budgets": token_budgets,
            "retrieval_budgets": retrieval_budgets,

            # 预算策略
            "budget_strategy": {
                "enforce_hard_limits": True,          # 强制执行硬性限制
                "truncate_on_overflow": True,         # 超限时截断而非失败
                "priority_based_allocation": True,    # 基于优先级分配
                "warn_on_80_percent": True,           # 达到 80% 时警告
            },

            # 证据分类预算（用于多层 RAG 证据融合）
            "evidence_budgets": self._build_evidence_budgets(is_fast_path),
        }

    @staticmethod
    def _build_evidence_budgets(is_fast_path: bool) -> Dict[str, Any]:
        """构建四类证据的 token 预算配额。"""
        if is_fast_path:
            return {
                "local_plot": {"max_tokens": 1500, "max_items": 4},
                "global_arc": {"max_tokens": 1200, "max_items": 3},
                "state_items": {"max_tokens": 800, "max_items": 3},
                "symbolic_items": {"max_tokens": 500, "max_items": 3},
                "total_max_tokens": 4000,
            }
        return {
            "local_plot": {"max_tokens": 3000, "max_items": 8},
            "global_arc": {"max_tokens": 2500, "max_items": 6},
            "state_items": {"max_tokens": 1500, "max_items": 5},
            "symbolic_items": {"max_tokens": 1500, "max_items": 5},
            "total_max_tokens": 8500,
        }

    def _infer_chapter_phase(
        self,
        *,
        chapter_number: int,
        total_chapters: int,
        outline_title: str,
        outline_summary: str,
    ) -> tuple[str, str]:
        normalized_text = f"{outline_title} {outline_summary}".lower()
        for phase, keywords in self._PHASE_KEYWORDS.items():
            if any(keyword.lower() in normalized_text for keyword in keywords):
                return phase, f"keyword:{phase}"

        if total_chapters <= 0:
            if chapter_number <= 2:
                return "setup", "fallback:early_chapter"
            return "development", "fallback:default"

        ratio = chapter_number / max(total_chapters, 1)
        if ratio <= 0.18:
            return "setup", f"ratio:{ratio:.2f}"
        if ratio >= 0.88:
            return "resolution", f"ratio:{ratio:.2f}"
        if ratio >= 0.68:
            return "climax", f"ratio:{ratio:.2f}"
        return "development", f"ratio:{ratio:.2f}"

    def _append_query(self, queries: List[str], value: str) -> None:
        normalized = " ".join(str(value or "").split())
        if normalized:
            queries.append(normalized)

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _dedupe_queries(self, queries: Sequence[str], limit: int) -> List[str]:
        result: List[str] = []
        seen = set()
        for item in queries:
            normalized = " ".join(str(item or "").split())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
            if len(result) >= limit:
                break
        return result
