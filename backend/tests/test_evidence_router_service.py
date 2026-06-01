import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.context_planner_service import ContextPlan
from app.services.evidence_router_service import EvidenceRouterService


def test_evidence_router_execute_builds_summary_from_mixed_sources():
    service = EvidenceRouterService()
    plan = ContextPlan.from_dict(
        {
            "intent": {"core_goal": "推进大战前夕的线索整合"},
            "chapter_phase": "climax",
            "retrieval_tasks": [
                {"task_id": "local_plot", "source": "local_plot_rag", "mode": "vector", "query_template": "{outline_title}"},
                {"task_id": "global_arc", "source": "global_arc_rag", "mode": "summary", "query_template": "{story_skeleton}"},
                {"task_id": "state", "source": "state_rag", "mode": "structured", "query_template": "{character_names}"},
                {"task_id": "symbolic", "source": "symbolic_rag", "mode": "structured", "query_template": "{foreshadowing}"},
            ],
            "skill_policies": [],
            "prompt_modules": ["chapter_goal", "rag_local"],
            "verification_tasks": ["continuity_check"],
            "budgets": {},
            "is_fast_path": False,
            "metadata": {},
        }
    )

    result = asyncio.run(
        service.execute(
            plan=plan,
            project_id="proj-1",
            chapter_number=9,
            user_id=7,
            history_context={
                "previous_summary": "上一章中主角得知决战情报。",
                "story_skeleton": "主线逐步逼近终局，旧线索开始交汇。",
            },
            rag_context={
                "chunks": ["片段一：旧敌再现。", "片段二：线索拼合。"],
                "summaries": ["第8章摘要：旧敌再现。"],
            },
            context_data={
                "world": "宗门大战一触即发",
                "current_realm": "化神境",
                "chapter_state_context": "林玄情绪压抑但决心已定。",
            },
            foreshadowing_data={
                "should_resolve": [
                    {"content": "黑玉碎片的来源", "chapter_number": 3, "urgency": "high"}
                ]
            },
            power_system_context="化神境以上不得强行突破。",
            relationship_context="- 林玄 <-> 苏璃: 同盟",
        )
    )

    summary = result.evidence_pack.graded_summary

    assert summary["plan_phase"] == "climax"
    assert summary["total_items"] >= 6
    assert summary["category_counts"]["local_plot"] >= 2
    assert summary["category_counts"]["global_arc"] >= 1
    assert summary["category_counts"]["state_items"] >= 1
    assert summary["category_counts"]["symbolic_items"] >= 1
    assert "local_plot_rag" in summary["sources"]
    assert "state_rag" in summary["sources"]
    assert summary["task_reports"]["local_plot_rag"]["status"] == "reused"


def test_evidence_router_route_local_plot_skips_without_task():
    service = EvidenceRouterService()
    plan = ContextPlan.from_dict(
        {
            "intent": {},
            "chapter_phase": "development",
            "retrieval_tasks": [
                {"task_id": "state", "source": "state_rag", "mode": "structured", "query_template": "{character_names}"},
            ],
            "skill_policies": [],
            "prompt_modules": [],
            "verification_tasks": [],
            "budgets": {},
            "is_fast_path": False,
            "metadata": {},
        }
    )

    routed = asyncio.run(
        service.route_local_plot(
            plan=plan,
            project_id="proj-2",
            user_id=1,
            queries=["终局前夜"],
            retrieval_mode="vector",
            llm_service=None,
            vector_store=None,
        )
    )

    assert routed["stats"]["status"] == "skipped"
    assert routed["stats"]["reason"] == "task_not_planned"


def test_evidence_router_route_global_arc_falls_back_to_completed_chapters():
    service = EvidenceRouterService()
    plan = ContextPlan.from_dict(
        {
            "intent": {},
            "chapter_phase": "development",
            "retrieval_tasks": [
                {"task_id": "global_arc", "source": "global_arc_rag", "mode": "summary", "query_template": "{story_skeleton}"},
            ],
            "skill_policies": [],
            "prompt_modules": [],
            "verification_tasks": [],
            "budgets": {},
            "is_fast_path": False,
            "metadata": {},
        }
    )

    items, report = asyncio.run(
        service.route_global_arc(
            plan=plan,
            history_context={
                "completed_chapters": [
                    {"chapter_number": 3, "title": "旧事重提", "summary": "旧线索开始重新汇合。"},
                    {"chapter_number": 4, "title": "暗流", "summary": "暗线继续推进。"},
                ]
            },
        )
    )

    assert report["status"] == "completed"
    assert len(items) == 2
    assert items[0].source == "global_arc_rag"


def test_evidence_router_route_state_builds_relationship_context_from_blueprint():
    service = EvidenceRouterService()
    plan = ContextPlan.from_dict(
        {
            "intent": {},
            "chapter_phase": "development",
            "retrieval_tasks": [
                {"task_id": "state", "source": "state_rag", "mode": "structured", "query_template": "{character_names}"},
            ],
            "skill_policies": [],
            "prompt_modules": [],
            "verification_tasks": [],
            "budgets": {},
            "is_fast_path": False,
            "metadata": {},
        }
    )

    payload, report = asyncio.run(
        service.route_state(
            plan=plan,
            project_id="proj-3",
            chapter_number=6,
            context_data={},
            relationship_context="",
            session=None,
            llm_service=None,
            prompt_service=None,
            blueprint_dict={
                "relationships": [
                    {"from": "林玄", "to": "苏璃", "relationship": "同盟", "description": "互相信任"},
                ]
            },
            involved_characters=["林玄", "苏璃"],
        )
    )

    assert report["status"] == "completed"
    assert "林玄 <-> 苏璃: 同盟" in payload["relationship_context"]


def test_evidence_router_format_filtered_context():
    service = EvidenceRouterService()
    filtered = type(
        "Filtered",
        (),
        {
            "plot_fuel": ["线索A"],
            "character_info": ["角色B"],
            "world_fragments": [],
            "narrative_techniques": ["技法C"],
            "warnings": ["警示D"],
        },
    )()

    text = service.format_filtered_context(filtered)

    assert "## 情节燃料" in text
    assert "线索A" in text
    assert "## 警示" in text


def test_evidence_router_prefetch_local_plot_skips_when_vector_store_disabled(monkeypatch):
    from app.services import evidence_router_service as module

    monkeypatch.setattr(module.settings, "qdrant_host", "")
    service = EvidenceRouterService()
    plan = ContextPlan.from_dict(
        {
            "intent": {},
            "chapter_phase": "development",
            "retrieval_tasks": [
                {"task_id": "local_plot", "source": "local_plot_rag", "mode": "vector", "query_template": "{outline_title}"},
            ],
            "skill_policies": [],
            "prompt_modules": [],
            "verification_tasks": [],
            "budgets": {},
            "is_fast_path": False,
            "metadata": {},
        }
    )

    routed = asyncio.run(
        service.prefetch_local_plot(
            plan=plan,
            project_id="proj-5",
            user_id=1,
            queries=["终局前夜"],
            retrieval_mode="vector",
        )
    )

    assert routed["stats"]["status"] == "skipped"
    assert routed["stats"]["reason"] == "vector_store_disabled"


def test_evidence_router_prefetch_symbolic_foreshadowing_builds_structured_payload(monkeypatch):
    from app.services import evidence_router_service as module

    class _SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    tracker = SimpleNamespace(
        get_foreshadowings_for_chapter=AsyncMock(
            return_value={
                "urgent": [SimpleNamespace(id=1, content="黑玉碎片来源", chapter_number=3)],
                "overdue": [],
                "due_soon": [SimpleNamespace(id=2, description="旧誓言需要兑现", chapter_number=6)],
                "related": [SimpleNamespace(id=3, content="旁支线索", chapter_number=2)],
            }
        )
    )

    monkeypatch.setattr(module, "AsyncSessionLocal", lambda: _SessionContext())
    monkeypatch.setattr(module, "LLMService", lambda session: SimpleNamespace())
    monkeypatch.setattr(module, "PromptService", lambda session: SimpleNamespace())
    monkeypatch.setattr(module, "ForeshadowingTrackerService", lambda session, llm, prompt: tracker)
    monkeypatch.setattr(
        module,
        "build_foreshadowing_urgency_brief",
        AsyncMock(return_value="伏笔摘要"),
    )

    service = EvidenceRouterService()
    brief, structured = asyncio.run(
        service.prefetch_symbolic_foreshadowing(
            project_id="proj-6",
            chapter_number=7,
        )
    )

    assert brief == "伏笔摘要"
    assert structured is not None
    assert structured["total_unresolved"] == 3
    assert structured["should_resolve"][0]["urgency"] == "high"
    assert structured["should_resolve"][1]["content"] == "旧誓言需要兑现"
