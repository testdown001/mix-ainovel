from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..core.config import settings
from ..db.session import AsyncSessionLocal
from .budget_enforcer_service import BudgetEnforcerService
from .chapter_context_service import ChapterContextService
from .context_planner_service import ContextPlan, EvidenceItem, GenerationEvidencePack
from .foreshadowing_tracker_service import ForeshadowingTrackerService
from .knowledge_retrieval_service import FilteredContext, KnowledgeRetrievalService
from .llm_service import LLMService
from .platinum_writing_context import build_foreshadowing_urgency_brief
from .prompt_service import PromptService
from .vector_store_service import VectorStoreService
from .writer_shared import create_vector_store_or_none


logger = logging.getLogger(__name__)


@dataclass
class RoutedEvidenceResult:
    evidence_pack: GenerationEvidencePack
    rag_context: Dict[str, Any] = field(default_factory=dict)
    knowledge_context: str = ""
    context_data: Dict[str, Any] = field(default_factory=dict)
    foreshadowing_data: Dict[str, Any] = field(default_factory=dict)
    power_system_context: str = ""
    relationship_context: str = ""
    task_reports: Dict[str, Any] = field(default_factory=dict)
    budget_reports: Dict[str, Any] = field(default_factory=dict)


class EvidenceRouterService:
    """按 ContextPlan 的 retrieval_tasks 执行多源证据路由，并执行预算控制。"""

    def __init__(self):
        self.budget_enforcer = BudgetEnforcerService()

    async def route_local_plot(
        self,
        *,
        plan: ContextPlan,
        project_id: str,
        user_id: int,
        queries: Sequence[str],
        retrieval_mode: str,
        llm_service: Optional[LLMService],
        vector_store: Optional[VectorStoreService],
        top_k_chunks: Optional[int] = None,
        top_k_summaries: Optional[int] = None,
    ) -> Dict[str, Any]:
        local_tasks = [task for task in plan.retrieval_tasks if task.source == "local_plot_rag"]
        if not local_tasks:
            return {
                "chunks": [],
                "summaries": [],
                "stats": {"status": "skipped", "reason": "task_not_planned"},
                "queries": [],
            }

        normalized_queries = self._normalize_queries(queries)
        if not normalized_queries:
            return {
                "chunks": [],
                "summaries": [],
                "stats": {"status": "skipped", "reason": "empty_queries"},
                "queries": [],
            }

        if not llm_service or not vector_store:
            return {
                "chunks": [],
                "summaries": [],
                "stats": {"status": "skipped", "reason": "missing_retrieval_dependencies"},
                "queries": list(normalized_queries),
            }

        max_items = max((task.max_items for task in local_tasks), default=5)
        context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)
        rag_result = await context_service.retrieve_multi_query(
            project_id=project_id,
            queries=list(normalized_queries),
            user_id=user_id,
            top_k_chunks=top_k_chunks or max_items,
            top_k_summaries=top_k_summaries,
            retrieval_mode=retrieval_mode,
        )
        chunk_texts = rag_result.chunk_texts() if rag_result.chunks else []
        summary_lines = rag_result.summary_lines() if rag_result.summaries else []
        return {
            "chunks": chunk_texts,
            "summaries": summary_lines,
            "stats": {
                "status": "completed",
                "queries": len(normalized_queries),
                "chunks": len(chunk_texts),
                "summaries": len(summary_lines),
                "mode": retrieval_mode,
            },
            "queries": list(normalized_queries),
        }

    async def prefetch_local_plot(
        self,
        *,
        plan: ContextPlan,
        project_id: str,
        user_id: int,
        queries: Sequence[str],
        retrieval_mode: str,
    ) -> Dict[str, Any]:
        if not settings.vector_store_enabled:
            return {
                "chunks": [],
                "summaries": [],
                "stats": {"status": "skipped", "reason": "vector_store_disabled"},
                "queries": [],
            }

        vector_store = create_vector_store_or_none()
        if vector_store is None:
            return {
                "chunks": [],
                "summaries": [],
                "stats": {"status": "skipped", "reason": "vector_store_unavailable"},
                "queries": [],
            }

        async with AsyncSessionLocal() as bg_session:
            bg_llm = LLMService(bg_session)
            return await self.route_local_plot(
                plan=plan,
                project_id=project_id,
                user_id=user_id,
                queries=queries,
                retrieval_mode=retrieval_mode,
                llm_service=bg_llm,
                vector_store=vector_store,
            )

    async def prefetch_symbolic_foreshadowing(
        self,
        *,
        project_id: str,
        chapter_number: int,
    ) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        async with AsyncSessionLocal() as bg_session:
            brief = await build_foreshadowing_urgency_brief(
                session=bg_session,
                project_id=project_id,
                chapter_number=chapter_number,
            )
            structured = None
            try:
                bg_llm = LLMService(bg_session)
                bg_prompt = PromptService(bg_session)
                tracker = ForeshadowingTrackerService(bg_session, bg_llm, bg_prompt)
                fs_data = await tracker.get_foreshadowings_for_chapter(project_id, chapter_number)
                structured = self._build_foreshadowing_payload(fs_data)
            except Exception as exc:
                logger.warning("结构化伏笔数据构建失败: %s", exc)
            return brief, structured

    async def route_two_stage(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
        writing_notes: str,
        pov_character: Optional[str],
        retrieval_mode: str,
        session: Optional[Any],
        llm_service: Optional[LLMService],
        vector_store: Optional[VectorStoreService],
    ) -> Dict[str, Any]:
        if not settings.vector_store_enabled:
            return {
                "knowledge_context": "",
                "stats": {"status": "skipped", "reason": "vector_store_disabled", "mode": "two_stage"},
            }

        if session is None or llm_service is None:
            return {
                "knowledge_context": "",
                "stats": {"status": "skipped", "reason": "missing_session_or_llm", "mode": "two_stage"},
            }

        if vector_store is None:
            from .writer_shared import create_vector_store_or_none

            vector_store = create_vector_store_or_none()
        if vector_store is None:
            return {
                "knowledge_context": "",
                "stats": {"status": "skipped", "reason": "vector_store_unavailable", "mode": "two_stage"},
            }

        retrieval_service = KnowledgeRetrievalService(session, llm_service, vector_store)
        try:
            filtered = await retrieval_service.retrieve_and_filter(
                project_id=project_id,
                chapter_number=chapter_number,
                user_id=user_id,
                pov_character=pov_character,
                user_guidance=writing_notes,
                top_k=settings.vector_top_k_chunks,
                retrieval_mode=retrieval_mode,
            )
        except Exception as exc:
            return {
                "knowledge_context": "",
                "stats": {
                    "status": "failed",
                    "reason": str(exc)[:200],
                    "mode": "two_stage",
                },
            }

        context_text = self.format_filtered_context(filtered)
        stats = dict(filtered.stats or {})
        stats["mode"] = "two_stage"
        stats["status"] = "completed"
        return {
            "knowledge_context": context_text or "",
            "stats": stats,
        }

    async def execute(
        self,
        *,
        plan: ContextPlan,
        project_id: str,
        chapter_number: int,
        user_id: int,
        history_context: Optional[Dict[str, Any]] = None,
        context_data: Optional[Dict[str, Any]] = None,
        foreshadowing_data: Optional[Dict[str, Any]] = None,
        power_system_context: Optional[str] = None,
        relationship_context: Optional[str] = None,
        rag_context: Optional[Dict[str, Any]] = None,
        knowledge_context: Optional[str] = None,
        local_queries: Optional[Sequence[str]] = None,
        retrieval_mode: str = "vector",
        session: Optional[Any] = None,
        prompt_service: Optional[PromptService] = None,
        llm_service: Optional[LLMService] = None,
        vector_store: Optional[VectorStoreService] = None,
        blueprint_dict: Optional[Dict[str, Any]] = None,
        involved_characters: Optional[List[str]] = None,
    ) -> RoutedEvidenceResult:
        history = history_context or {}
        ctx = dict(context_data or {})
        foreshadowing = dict(foreshadowing_data or {})
        task_sources = {task.source for task in plan.retrieval_tasks}
        routed_rag_context = dict(rag_context or {})
        routed_knowledge_context = str(knowledge_context or "")
        routed_context_data = dict(ctx)
        routed_foreshadowing_data = dict(foreshadowing)
        routed_power_system_context = str(power_system_context or "")
        routed_relationship_context = str(relationship_context or "")
        task_reports: Dict[str, Any] = {}

        if "local_plot_rag" in task_sources and not (routed_rag_context or routed_knowledge_context):
            routed_local = await self.route_local_plot(
                plan=plan,
                project_id=project_id,
                user_id=user_id,
                queries=local_queries or [],
                retrieval_mode=retrieval_mode,
                llm_service=llm_service,
                vector_store=vector_store,
            )
            routed_rag_context = {
                "chunks": list(routed_local.get("chunks") or []),
                "summaries": list(routed_local.get("summaries") or []),
            }
            task_reports["local_plot_rag"] = {
                **dict(routed_local.get("stats") or {}),
                "queries": list(routed_local.get("queries") or []),
            }
        elif "local_plot_rag" in task_sources:
            task_reports["local_plot_rag"] = {
                "status": "reused",
                "queries": list(self._normalize_queries(local_queries or [])),
                "chunks": len(routed_rag_context.get("chunks") or []),
                "summaries": len(routed_rag_context.get("summaries") or []),
            }

        if "local_plot_rag" in task_sources and routed_knowledge_context:
            task_reports["two_stage_rag"] = {
                "status": "reused",
                "mode": "two_stage",
            }

        evidence_pack = GenerationEvidencePack()

        if "local_plot_rag" in task_sources:
            self._append_local_plot(
                evidence_pack=evidence_pack,
                rag_context=routed_rag_context,
                knowledge_context=routed_knowledge_context,
            )

        if "global_arc_rag" in task_sources:
            global_items, global_report = await self.route_global_arc(
                plan=plan,
                history_context=history,
                project_id=project_id,
                chapter_number=chapter_number,
                session=session,
                llm_service=llm_service,
            )
            evidence_pack.global_arc.extend(global_items)
            task_reports["global_arc_rag"] = {
                **global_report,
                "items": len(global_items),
            }

        if "state_rag" in task_sources:
            state_payload, state_report = await self.route_state(
                plan=plan,
                project_id=project_id,
                chapter_number=chapter_number,
                context_data=routed_context_data,
                relationship_context=routed_relationship_context,
                session=session,
                llm_service=llm_service,
                prompt_service=prompt_service,
                blueprint_dict=blueprint_dict,
                involved_characters=involved_characters,
            )
            routed_context_data.update(state_payload.get("context_data") or {})
            if state_payload.get("relationship_context"):
                routed_relationship_context = str(state_payload.get("relationship_context") or "")

            # temporal_snapshot 模式：使用 TemporalStateService 转换为 EvidenceItem
            if "snapshot" in state_payload:
                from .temporal_state_service import TemporalStateService

                temporal = TemporalStateService(session)
                budget_tokens = self._get_state_budget(evidence_pack)
                evidence_pack.state_items.extend(
                    temporal.to_evidence_items(state_payload["snapshot"], budget_tokens=budget_tokens)
                )
            else:
                self._append_state_items(
                    evidence_pack=evidence_pack,
                    context_data=routed_context_data,
                    relationship_context=routed_relationship_context,
                )
            task_reports["state_rag"] = {
                **state_report,
                "items": len(evidence_pack.state_items),
            }

        if "symbolic_rag" in task_sources:
            symbolic_payload, symbolic_report = await self.route_symbolic(
                plan=plan,
                project_id=project_id,
                chapter_number=chapter_number,
                foreshadowing_data=routed_foreshadowing_data,
                power_system_context=routed_power_system_context,
                session=session,
                llm_service=llm_service,
                prompt_service=prompt_service,
            )
            routed_foreshadowing_data = dict(symbolic_payload.get("foreshadowing_data") or routed_foreshadowing_data)
            if symbolic_payload.get("power_system_context"):
                routed_power_system_context = str(symbolic_payload.get("power_system_context") or "")
            self._append_symbolic_items(
                evidence_pack=evidence_pack,
                foreshadowing_data=routed_foreshadowing_data,
                power_system_context=routed_power_system_context,
            )
            task_reports["symbolic_rag"] = {
                **symbolic_report,
                "items": len(evidence_pack.symbolic_items),
            }

        budget_report = self._enforce_evidence_budgets(evidence_pack, plan.budgets)
        if budget_report:
            task_reports["evidence_budget"] = budget_report

        evidence_pack.graded_summary = self.build_summary(
            plan=plan,
            evidence_pack=evidence_pack,
            task_reports=task_reports,
        )
        return RoutedEvidenceResult(
            evidence_pack=evidence_pack,
            rag_context=routed_rag_context,
            knowledge_context=routed_knowledge_context,
            context_data=routed_context_data,
            foreshadowing_data=routed_foreshadowing_data,
            power_system_context=routed_power_system_context,
            relationship_context=routed_relationship_context,
            task_reports=task_reports,
        )

    @staticmethod
    def format_filtered_context(filtered: FilteredContext) -> Optional[str]:
        if not filtered:
            return None

        sections = []
        if filtered.plot_fuel:
            sections.append("## 情节燃料\n" + "\n".join(f"- {item}" for item in filtered.plot_fuel))
        if filtered.character_info:
            sections.append("## 角色信息\n" + "\n".join(f"- {item}" for item in filtered.character_info))
        if filtered.world_fragments:
            sections.append("## 世界碎片\n" + "\n".join(f"- {item}" for item in filtered.world_fragments))
        if filtered.narrative_techniques:
            sections.append("## 叙事技法\n" + "\n".join(f"- {item}" for item in filtered.narrative_techniques))
        if filtered.warnings:
            sections.append("## 警示\n" + "\n".join(f"- {item}" for item in filtered.warnings))
        return "\n\n".join(sections) if sections else None

    async def route_global_arc(
        self,
        *,
        plan: ContextPlan,
        history_context: Dict[str, Any],
        project_id: Optional[str] = None,
        chapter_number: Optional[int] = None,
        session: Optional[Any] = None,
        llm_service: Optional[LLMService] = None,
    ) -> tuple[List[EvidenceItem], Dict[str, Any]]:
        tasks = [task for task in plan.retrieval_tasks if task.source == "global_arc_rag"]
        if not tasks:
            return [], {"status": "skipped", "reason": "task_not_planned"}

        items: List[EvidenceItem] = []
        self._append_global_arc_items(items=items, history_context=history_context)

        # 注入卷级摘要和书级摘要
        volume_count = 0
        has_book_summary = False
        if session and llm_service and project_id and chapter_number:
            try:
                from .volume_summary_service import VolumeSummaryService
                vol_service = VolumeSummaryService(session, llm_service)
                vol_summaries = await vol_service.get_relevant_volume_summaries(
                    project_id, chapter_number, max_volumes=3,
                )
                for vs in vol_summaries:
                    items.append(
                        EvidenceItem(
                            source="global_arc_rag",
                            title=vs["title"],
                            content=vs["summary"],
                            score=0.75,
                            metadata={"type": "volume_summary", "volume_number": vs["volume_number"]},
                        )
                    )
                    volume_count += 1
            except Exception as exc:
                logger.warning("卷级摘要检索失败: %s", exc)

            try:
                from .book_summary_service import BookSummaryService
                book_service = BookSummaryService(session, llm_service)
                book_summary = await book_service.get_book_summary(project_id)
                if book_summary:
                    items.append(
                        EvidenceItem(
                            source="global_arc_rag",
                            title="全书摘要",
                            content=book_summary,
                            score=0.85,
                            metadata={"type": "book_summary"},
                        )
                    )
                    has_book_summary = True
            except Exception as exc:
                logger.warning("书级摘要检索失败: %s", exc)

        if not items:
            completed = history_context.get("completed_chapters") or []
            for chapter in completed[-3:]:
                summary = str((chapter or {}).get("summary") or "").strip()
                if not summary:
                    continue
                title = str((chapter or {}).get("title") or f"第{chapter.get('chapter_number')}章")
                items.append(
                    EvidenceItem(
                        source="global_arc_rag",
                        title=title,
                        content=summary,
                        score=0.62,
                    )
                )

        report = {"status": "completed" if items else "skipped", "reason": None if items else "empty_history"}
        if volume_count:
            report["volume_summaries"] = volume_count
        if has_book_summary:
            report["book_summary"] = True
        return items, report

    async def route_state(
        self,
        *,
        plan: ContextPlan,
        project_id: str,
        chapter_number: int,
        context_data: Dict[str, Any],
        relationship_context: str,
        session: Optional[Any],
        llm_service: Optional[LLMService],
        prompt_service: Optional[PromptService],
        blueprint_dict: Optional[Dict[str, Any]],
        involved_characters: Optional[List[str]],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        tasks = [task for task in plan.retrieval_tasks if task.source == "state_rag"]
        if not tasks:
            return {"context_data": context_data, "relationship_context": relationship_context}, {"status": "skipped", "reason": "task_not_planned"}

        resolved_context = dict(context_data)
        resolved_relationship = relationship_context
        active_fetches = 0

        # temporal_snapshot 模式：使用 TemporalStateService 聚合全量时序数据
        state_task = tasks[0] if tasks else None
        if state_task and state_task.mode == "temporal_snapshot" and session:
            from .temporal_state_service import TemporalStateService

            temporal = TemporalStateService(session)
            snapshot = await temporal.get_world_snapshot(
                project_id=project_id,
                chapter_number=chapter_number,
                involved_characters=involved_characters,
                blueprint_dict=blueprint_dict,
            )
            return {
                "context_data": resolved_context,
                "relationship_context": resolved_relationship,
                "snapshot": snapshot,
            }, {"status": "completed", "mode": "temporal_snapshot"}

        if session and llm_service and prompt_service and not resolved_context.get("chapter_state_context"):
            from .memory_layer_service import MemoryLayerService

            memory_service = MemoryLayerService(session, llm_service, prompt_service)
            state_text = await memory_service.build_chapter_state_context(
                project_id=project_id,
                chapter_number=chapter_number,
                involved_characters=involved_characters,
            )
            if state_text:
                resolved_context["chapter_state_context"] = state_text
                active_fetches += 1

            try:
                states = await memory_service.get_all_character_states(project_id, chapter_number)
                power_levels = [str(state.power_level).strip() for state in states if getattr(state, "power_level", None)]
                if power_levels and not resolved_context.get("current_realm"):
                    unique_levels: List[str] = []
                    for level in power_levels:
                        if level and level not in unique_levels:
                            unique_levels.append(level)
                    resolved_context["current_realm"] = " / ".join(unique_levels[:3])
            except Exception:
                pass

        if blueprint_dict and not resolved_relationship:
            rels = blueprint_dict.get("relationships", []) or []
            rel_lines: List[str] = []
            for relation in rels[:20]:
                from_name = relation.get("from", relation.get("character1", ""))
                to_name = relation.get("to", relation.get("character2", ""))
                rel_type = relation.get("relationship", relation.get("type", ""))
                desc = relation.get("description", "")
                line = f"- {from_name} <-> {to_name}: {rel_type}"
                if desc:
                    line += f" ({desc[:60]})"
                rel_lines.append(line)
            if rel_lines:
                resolved_relationship = "\n".join(rel_lines)
                active_fetches += 1

        return {
            "context_data": resolved_context,
            "relationship_context": resolved_relationship,
        }, {
            "status": "completed" if active_fetches or resolved_context or resolved_relationship else "skipped",
            "active_fetches": active_fetches,
        }

    async def route_symbolic(
        self,
        *,
        plan: ContextPlan,
        project_id: str,
        chapter_number: int,
        foreshadowing_data: Dict[str, Any],
        power_system_context: str,
        session: Optional[Any],
        llm_service: Optional[LLMService],
        prompt_service: Optional[PromptService],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        tasks = [task for task in plan.retrieval_tasks if task.source == "symbolic_rag"]
        if not tasks:
            return {
                "foreshadowing_data": foreshadowing_data,
                "power_system_context": power_system_context,
            }, {"status": "skipped", "reason": "task_not_planned"}

        resolved_foreshadowing = dict(foreshadowing_data)
        resolved_power_system_context = power_system_context
        active_fetches = 0

        if session and llm_service and prompt_service and not resolved_foreshadowing:
            tracker = ForeshadowingTrackerService(session, llm_service, prompt_service)
            fs_data = await tracker.get_foreshadowings_for_chapter(project_id, chapter_number)
            resolved_foreshadowing = self._build_foreshadowing_payload(fs_data)
            active_fetches += 1

        if session and not resolved_power_system_context:
            from .power_system_service import PowerSystemService

            ps_service = PowerSystemService(session)
            systems = await ps_service.get_power_systems_by_project(project_id)
            if systems:
                parts: List[str] = []
                for system in systems:
                    lines = [f"### {system.name}"]
                    if system.description:
                        lines.append(f"规则: {system.description}")
                    for level in getattr(system, "levels", []) or []:
                        detail = f"- {level.name}"
                        if getattr(level, "abilities", None):
                            detail += f" | 能力: {level.abilities}"
                        if getattr(level, "limitations", None):
                            detail += f" | 限制: {level.limitations}"
                        lines.append(detail)
                    parts.append("\n".join(lines))
                resolved_power_system_context = "\n\n".join(parts)
                active_fetches += 1

        return {
            "foreshadowing_data": resolved_foreshadowing,
            "power_system_context": resolved_power_system_context,
        }, {
            "status": "completed" if active_fetches or resolved_foreshadowing or resolved_power_system_context else "skipped",
            "active_fetches": active_fetches,
        }

    def build_summary(
        self,
        *,
        plan: ContextPlan,
        evidence_pack: GenerationEvidencePack,
        task_reports: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        categories = {
            "local_plot": evidence_pack.local_plot,
            "global_arc": evidence_pack.global_arc,
            "state_items": evidence_pack.state_items,
            "symbolic_items": evidence_pack.symbolic_items,
        }
        category_counts = {name: len(items) for name, items in categories.items()}
        total_items = sum(category_counts.values())
        return {
            "plan_phase": plan.chapter_phase,
            "is_fast_path": plan.is_fast_path,
            "total_items": total_items,
            "category_counts": category_counts,
            "sources": self._unique_sources(categories.values()),
            "top_titles": self._top_titles(categories.values(), limit=6),
            "evidence_samples": self._evidence_samples(categories, limit=8),
            "retrieval_task_count": len(plan.retrieval_tasks),
            "task_reports": dict(task_reports or {}),
        }

    @staticmethod
    def _build_foreshadowing_payload(fs_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        resolved = fs_data or {}
        should_resolve: List[Dict[str, Any]] = []
        for category in ("urgent", "overdue", "due_soon"):
            urgency = "high" if category == "urgent" else "medium"
            for fs in resolved.get(category, []) or []:
                should_resolve.append(
                    {
                        "id": getattr(fs, "id", None),
                        "content": getattr(fs, "content", "") or getattr(fs, "description", ""),
                        "chapter_number": getattr(fs, "chapter_number", None),
                        "urgency": urgency,
                    }
                )

        total_unresolved = sum(
            len(resolved.get(key, []) or [])
            for key in ("urgent", "due_soon", "overdue", "related")
        )
        return {
            "should_resolve": should_resolve[:10],
            "should_plant": [],
            "total_unresolved": total_unresolved,
        }

    def _append_local_plot(
        self,
        *,
        evidence_pack: GenerationEvidencePack,
        rag_context: Dict[str, Any],
        knowledge_context: str,
    ) -> None:
        for index, chunk in enumerate(rag_context.get("chunks") or [], start=1):
            content = chunk if isinstance(chunk, str) else str(chunk.get("content") or "")
            if not content:
                continue
            score = 0.0
            if isinstance(chunk, dict):
                try:
                    score = float(chunk.get("score") or 0.0)
                except (TypeError, ValueError):
                    score = 0.0
            evidence_pack.local_plot.append(
                EvidenceItem(
                    source="local_plot_rag",
                    title=f"剧情片段 {index}",
                    content=content,
                    score=score,
                )
            )

        for index, summary in enumerate(rag_context.get("summaries") or [], start=1):
            content = str(summary or "").strip()
            if not content:
                continue
            evidence_pack.local_plot.append(
                EvidenceItem(
                    source="local_plot_rag",
                    title=f"章节摘要 {index}",
                    content=content,
                    score=0.6,
                )
            )

        if knowledge_context:
            evidence_pack.local_plot.append(
                EvidenceItem(
                    source="local_plot_rag",
                    title="精筛上下文",
                    content=knowledge_context,
                    score=0.8,
                )
            )

    def _append_global_arc(
        self,
        *,
        evidence_pack: GenerationEvidencePack,
        history_context: Dict[str, Any],
    ) -> None:
        self._append_global_arc_items(items=evidence_pack.global_arc, history_context=history_context)

    def _append_global_arc_items(
        self,
        *,
        items: List[EvidenceItem],
        history_context: Dict[str, Any],
    ) -> None:
        for title, content in (
            ("上一章摘要", history_context.get("previous_summary")),
            ("上一章结尾", history_context.get("previous_tail")),
            ("故事骨架", history_context.get("story_skeleton")),
        ):
            normalized = str(content or "").strip()
            if not normalized:
                continue
            items.append(
                EvidenceItem(
                    source="global_arc_rag",
                    title=title,
                    content=normalized,
                    score=0.7,
                )
            )

    def _get_state_budget(self, evidence_pack: GenerationEvidencePack) -> int:
        """获取 state_items 的 token 预算。"""
        # 从 _build_evidence_budgets 的 balanced 预算中取 state_items 分配
        # balanced: state_items = 2000 tokens (来自 context_planner_service)
        return 2000

    def _append_state_items(
        self,
        *,
        evidence_pack: GenerationEvidencePack,
        context_data: Dict[str, Any],
        relationship_context: Optional[str],
    ) -> None:
        for title, content in (
            ("世界观", context_data.get("world")),
            ("当前修为", context_data.get("current_realm")),
            ("修炼体系摘要", context_data.get("cultivation_system")),
            ("角色状态", context_data.get("chapter_state_context")),
        ):
            normalized = str(content or "").strip()
            if not normalized:
                continue
            evidence_pack.state_items.append(
                EvidenceItem(
                    source="state_rag",
                    title=title,
                    content=normalized,
                    score=0.65,
                )
            )

        if relationship_context:
            evidence_pack.state_items.append(
                EvidenceItem(
                    source="state_rag",
                    title="角色关系网",
                    content=relationship_context,
                    score=0.75,
                )
            )

    def _append_symbolic_items(
        self,
        *,
        evidence_pack: GenerationEvidencePack,
        foreshadowing_data: Dict[str, Any],
        power_system_context: Optional[str],
    ) -> None:
        if power_system_context:
            evidence_pack.symbolic_items.append(
                EvidenceItem(
                    source="symbolic_rag",
                    title="力量体系约束",
                    content=power_system_context,
                    score=0.85,
                )
            )

        for item in foreshadowing_data.get("should_resolve") or []:
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            chapter_number = item.get("chapter_number")
            label = f"待回收伏笔（第{chapter_number}章）" if chapter_number else "待回收伏笔"
            evidence_pack.symbolic_items.append(
                EvidenceItem(
                    source="symbolic_rag",
                    title=label,
                    content=content,
                    score=0.9 if item.get("urgency") == "high" else 0.7,
                    metadata={"urgency": item.get("urgency")},
                )
            )

        if foreshadowing_data.get("brief"):
            evidence_pack.symbolic_items.append(
                EvidenceItem(
                    source="symbolic_rag",
                    title="伏笔摘要",
                    content=str(foreshadowing_data["brief"]),
                    score=0.6,
                )
            )

    def _enforce_evidence_budgets(
        self,
        evidence_pack: GenerationEvidencePack,
        budgets: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """对证据包的四个分类执行 token 预算控制。

        在每个分类内按 score 降序排列，超出预算的项被截断或丢弃。
        返回预算执行报告，无预算配置时返回 None。
        """
        evidence_budgets = (budgets or {}).get("evidence_budgets")
        if not evidence_budgets:
            return None

        category_map = {
            "local_plot": evidence_pack.local_plot,
            "global_arc": evidence_pack.global_arc,
            "state_items": evidence_pack.state_items,
            "symbolic_items": evidence_pack.symbolic_items,
        }

        report: Dict[str, Any] = {}
        total_before = 0
        total_after = 0

        for category_name, items in category_map.items():
            cat_budget = evidence_budgets.get(category_name)
            if not cat_budget or not items:
                continue

            max_tokens = cat_budget.get("max_tokens", 10000)
            max_items = cat_budget.get("max_items", 20)

            before_count = len(items)
            before_tokens = sum(
                self.budget_enforcer.estimate_tokens(item.content) for item in items
            )
            total_before += before_tokens

            # 按 score 降序排序
            items.sort(key=lambda x: x.score, reverse=True)

            # 限制数量
            if len(items) > max_items:
                items[:] = items[:max_items]

            # 限制 token 总量
            kept: List[EvidenceItem] = []
            used_tokens = 0
            truncated = 0

            for item in items:
                item_tokens = self.budget_enforcer.estimate_tokens(item.content)
                if used_tokens + item_tokens <= max_tokens:
                    kept.append(item)
                    used_tokens += item_tokens
                else:
                    remaining = max_tokens - used_tokens
                    if remaining > 100:
                        truncated_text, was_truncated = self.budget_enforcer.truncate_to_budget(
                            item.content, remaining
                        )
                        if was_truncated:
                            truncated += 1
                        item.content = truncated_text
                        kept.append(item)
                        used_tokens += self.budget_enforcer.estimate_tokens(truncated_text)
                    break

            items[:] = kept
            total_after += used_tokens

            if before_count != len(kept) or truncated > 0:
                report[category_name] = {
                    "before": before_count,
                    "after": len(kept),
                    "dropped": before_count - len(kept),
                    "truncated": truncated,
                    "tokens_before": before_tokens,
                    "tokens_after": used_tokens,
                    "max_tokens": max_tokens,
                }

        total_max = evidence_budgets.get("total_max_tokens", 0)
        if total_max and total_before > 0:
            report["total"] = {
                "tokens_before": total_before,
                "tokens_after": total_after,
                "max_tokens": total_max,
                "utilization": round(total_after / total_max, 2) if total_max else 0,
            }

        return report if report else None

    def _normalize_queries(self, queries: Sequence[str]) -> List[str]:
        result: List[str] = []
        seen = set()
        for item in queries:
            normalized = " ".join(str(item or "").split())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    def _unique_sources(self, groups: Iterable[List[EvidenceItem]]) -> List[str]:
        result: List[str] = []
        seen = set()
        for items in groups:
            for item in items:
                if item.source in seen:
                    continue
                seen.add(item.source)
                result.append(item.source)
        return result

    def _top_titles(self, groups: Iterable[List[EvidenceItem]], limit: int) -> List[str]:
        titles: List[str] = []
        for items in groups:
            for item in items:
                title = str(item.title or "").strip()
                if title:
                    titles.append(title)
                if len(titles) >= limit:
                    return titles
        return titles

    def _evidence_samples(self, categories: Dict[str, List[EvidenceItem]], limit: int) -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        for category, items in categories.items():
            for item in items:
                samples.append(
                    {
                        "category": category,
                        "source": item.source,
                        "title": item.title,
                        "score": item.score,
                        "content": (item.content or "")[:500],
                    }
                )
                if len(samples) >= limit:
                    return samples
        return samples
