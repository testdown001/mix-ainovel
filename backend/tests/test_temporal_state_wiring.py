"""任务 X2：temporal_state 接通回归测试（2026-07）。

锁定三处修复：
1. TemporalStateService.get_world_snapshot 串行化 —— 所有 _fetch_* 共享同一
   AsyncSession，SQLAlchemy 异步会话禁并发，gather 改为串行 await；
   另 _fetch_story_time（唯一写库的抓取）失败后尽力 rollback 复位 session，
   保证降级后同 session 的后续查询（如 build_chapter_state_context）仍可用。
2. EvidenceRouterService.route_state 的 temporal_snapshot 分支改「补充而非替代」——
   必须与 structured 路径一样产出 chapter_state_context / current_realm /
   relationship_context（蓝图关系网兜底），时序快照仅额外通过 payload["snapshot"]
   进入 evidence_pack.state_items 诊断层。
3. pipeline_orchestrator.generate_chapter 的 planner_flow_config 透传
   enable_temporal_state —— 否则 ContextPlanner 的 state 任务 mode 恒 structured，
   temporal_state_service 全文件从未执行。
"""
import asyncio
import inspect
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

# 避免 SQLAlchemy mapper 未初始化导致 KeyError
import app.models.user_quota  # noqa: F401

from app.models.memory_layer import CharacterState, StoryTimeTracker
from app.services.context_planner_service import (
    ContextPlan,
    ContextPlannerService,
    RetrievalTask,
)
from app.services.evidence_router_service import EvidenceRouterService
from app.services.pipeline_config_service import PipelineConfigService
from app.services.temporal_state_service import TemporalStateService


class _DummySession:
    async def execute(self, stmt):
        class _ScalarResult:
            def scalar_one_or_none(self):
                return None

            def scalars(self):
                return self

            def all(self):
                return []

            def first(self):
                return None

        return _ScalarResult()


def _resolve(flow_config):
    service = PipelineConfigService(_DummySession())
    return asyncio.run(service.resolve_config(flow_config))


# ── 1. 配置矩阵：enable_temporal_state 纯 preset 驱动 ──


def test_temporal_state_preset_matrix():
    assert _resolve({"preset": "standard"}).enable_temporal_state is True
    assert _resolve({"preset": "premium"}).enable_temporal_state is True
    assert _resolve({"preset": "fast"}).enable_temporal_state is False


# ── 2. 读侧规划：state 任务 mode 落到 temporal_snapshot ──


def _planner_flow(config):
    # 镜像 pipeline_orchestrator.generate_chapter 的 planner_flow_config（含新键 enable_temporal_state）
    return {
        "preset": config.preset,
        "selected_skills": [],
        "skill_policies": [],
        "enable_rag": config.enable_rag,
        "enable_memory": config.enable_memory,
        "enable_state_tracking": config.enable_state_tracking,
        "enable_temporal_state": config.enable_temporal_state,
        "enable_fast_path": config.enable_fast_path,
        "enable_consistency": config.enable_consistency,
        "enable_foreshadowing": config.enable_foreshadowing,
        "enable_constitution": config.enable_constitution,
        "enable_faction": config.enable_faction,
        "enable_power_system": config.enable_power_system,
        "enable_character_relationships": config.enable_character_relationships,
        "enable_polish": config.enable_polish,
        "enable_reader_sim": config.enable_reader_sim,
        "enable_self_critique": config.enable_self_critique,
        "enable_six_dimension": config.enable_six_dimension,
        "enable_mission_brief": config.enable_mission_brief,
        "rag_mode": config.rag_mode,
        "rag_retrieval_mode": config.rag_retrieval_mode,
    }


def _build_plan(config, chapter_number=5):
    planner = ContextPlannerService()
    return asyncio.run(
        planner.build_plan(
            project_id="p1",
            chapter_number=chapter_number,
            writing_notes="推进冲突",
            flow_config=_planner_flow(config),
            blueprint={
                "characters": [{"name": "林玄"}],
                "chapter_outline": [{"chapter_number": idx} for idx in range(1, 12)],
            },
            outline_data={
                "chapter_number": chapter_number,
                "title": "第五章",
                "summary": "冲突推进",
            },
            history_context={"previous_summary": "主角初入宗门。"},
        )
    )


def _state_task(plan):
    tasks = [t for t in plan.retrieval_tasks if t.source == "state_rag"]
    assert tasks, "state_rag 任务应被规划"
    return tasks[0]


def test_build_plan_state_mode_temporal_for_standard_and_premium():
    for preset in ("standard", "premium"):
        plan = _build_plan(_resolve({"preset": preset}))
        assert _state_task(plan).mode == "temporal_snapshot", preset


def test_build_plan_state_mode_structured_for_fast():
    # fast 不受影响：state 任务照旧（chapter>1 触发），但 mode 仍为 structured
    plan = _build_plan(_resolve({"preset": "fast"}))
    assert _state_task(plan).mode == "structured"


def test_orchestrator_planner_flow_config_passes_enable_temporal_state():
    # 接线回归：orchestrator 若漏传该键，planner 侧 mode 恒 structured（本 bug 根因）
    from app.services.pipeline_orchestrator import PipelineOrchestrator

    source = inspect.getsource(PipelineOrchestrator.generate_chapter)
    assert '"enable_temporal_state": config.enable_temporal_state' in source


# ── 3. 证据阶段：temporal 是补充而非替代 ──


_BLUEPRINT = {
    "relationships": [
        {"from": "林玄", "to": "苏璃", "relationship": "师徒", "description": "亦师亦友"},
    ]
}


def _make_plan(state_mode):
    return ContextPlan(
        intent={},
        chapter_phase="development",
        retrieval_tasks=[
            RetrievalTask(
                task_id="state_snapshot",
                source="state_rag",
                mode=state_mode,
                query_template="{character_names}\n{writing_notes}",
            )
        ],
        skill_policies=[],
        prompt_modules=[],
        verification_tasks=[],
    )


async def _seed_states(db_session):
    from app.models.novel import Chapter, ChapterVersion, NovelProject
    from app.services.chapter_derivation_service import build_source_ref
    db_session.add(NovelProject(id="p1", user_id=1, title="时序状态测试"))
    for number in (3, 4):
        chapter = Chapter(project_id="p1", chapter_number=number, revision_id=1)
        db_session.add(chapter)
        await db_session.flush()
        version = ChapterVersion(chapter_id=chapter.id, content=f"第{number}章已确认正文")
        db_session.add(version)
        await db_session.flush()
        chapter.selected_version_id = version.id
    await db_session.flush()
    sources = {number: (await build_source_ref(db_session, project_id="p1", chapter_number=number)).model_dump()
               for number in (3, 4)}
    # CharacterState.id 是纯 BigInteger 主键，sqlite 播种须显式赋 id
    db_session.add(
        CharacterState(
            id=1,
            project_id="p1",
            character_id=1,
            character_name="林玄",
            chapter_number=4,
            extra={"provenance": sources[4]},
            location="青云山",
            emotion="坚定",
            health_status="healthy",
            power_level="金丹期",
            current_goals=["夺回宗门"],
        )
    )
    db_session.add(
        CharacterState(
            id=2,
            project_id="p1",
            character_id=2,
            character_name="苏璃",
            chapter_number=3,
            extra={"provenance": sources[3]},
            location="南荒",
            emotion="担忧",
            health_status="injured",
        )
    )
    await db_session.commit()


async def _route(db_session, state_mode):
    router = EvidenceRouterService()
    return await router.route_state(
        plan=_make_plan(state_mode),
        project_id="p1",
        chapter_number=5,
        context_data={},
        relationship_context="",
        session=db_session,
        llm_service=MagicMock(),
        prompt_service=MagicMock(),
        blueprint_dict=_BLUEPRINT,
        involved_characters=["林玄"],
    )


@pytest.mark.asyncio
async def test_route_state_temporal_supplements_structured_products(db_session):
    await _seed_states(db_session)

    temporal_payload, temporal_report = await _route(db_session, "temporal_snapshot")
    structured_payload, _ = await _route(db_session, "structured")

    # 1) temporal 模式必须照常产出 [角色当前状态] 数据源与蓝图关系网兜底
    temporal_state_ctx = temporal_payload["context_data"].get("chapter_state_context")
    assert temporal_state_ctx and "林玄" in temporal_state_ctx
    assert temporal_payload["relationship_context"] and "林玄" in temporal_payload["relationship_context"]

    # 2) 与 structured 模式产物逐项一致（补充而非替代）
    assert temporal_state_ctx == structured_payload["context_data"].get("chapter_state_context")
    assert temporal_payload["relationship_context"] == structured_payload["relationship_context"]
    assert temporal_payload["context_data"].get("current_realm") == structured_payload["context_data"].get("current_realm")

    # 3) 时序快照仅额外补充（→ evidence_pack.state_items 诊断层），structured 不带
    assert "snapshot" in temporal_payload
    assert "snapshot" not in structured_payload
    assert temporal_report.get("mode") == "temporal_snapshot"
    snapshot = temporal_payload["snapshot"]
    assert any(c["name"] == "林玄" for c in snapshot.characters)


# ── 4. get_world_snapshot 串行化后功能正常 ──


@pytest.mark.asyncio
async def test_get_world_snapshot_serial_with_seeded_data(db_session):
    await _seed_states(db_session)
    from app.services.chapter_derivation_service import build_source_ref
    source = (await build_source_ref(db_session, project_id="p1", chapter_number=4)).model_dump()
    db_session.add(StoryTimeTracker(id=1, project_id="p1", chapter_time_map={"4": "第七日"},
                                  extra={"chapter_sources": {"4": source}}))
    await db_session.commit()

    service = TemporalStateService(db_session)
    snapshot = await service.get_world_snapshot(
        "p1",
        5,
        involved_characters=["林玄"],
        blueprint_dict={
            "relationships": [
                {"from_name": "林玄", "to_name": "苏璃", "relationship_type": "师徒", "description": "亦师亦友"}
            ]
        },
    )

    names = [c["name"] for c in snapshot.characters]
    assert names[0] == "林玄"  # involved 优先
    assert "苏璃" in names
    assert {"name": "林玄", "power_level": "金丹期"} in snapshot.power_landscape
    assert snapshot.story_time.get("chapter_time_map") == {"4": "第七日"}
    assert "林玄" in snapshot.relationship_network


@pytest.mark.asyncio
async def test_get_world_snapshot_empty_db_no_raise_and_session_stays_usable(db_session):
    service = TemporalStateService(db_session)
    snapshot = await service.get_world_snapshot("p-none", 3)

    assert snapshot.characters == []
    assert snapshot.recent_events == []
    assert snapshot.pending_chains == []

    # 空库下 _fetch_story_time 的写入在 sqlite 上可能失败（纯 BigInteger 主键无自增），
    # 降级后共享 session 必须仍可用（rollback 复位），否则下游状态查询全部失效
    result = await db_session.execute(select(CharacterState))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_temporal_snapshot_rejects_current_future_and_legacy_state(db_session):
    await _seed_states(db_session)
    from app.services.chapter_derivation_service import build_source_ref
    source = (await build_source_ref(db_session, project_id="p1", chapter_number=4)).model_dump()
    db_session.add_all([
        CharacterState(id=3, project_id="p1", character_id=3, character_name="未来角色", chapter_number=5,
                       emotion="第5章结果", extra={"provenance": source}),
        CharacterState(id=4, project_id="p1", character_id=4, character_name="旧脏数据", chapter_number=2,
                       emotion="没有来源"),
        StoryTimeTracker(id=1, project_id="p1", chapter_time_map={"4":"第七日", "5":"未来日", "1":"未验证"},
                         extra={"chapter_sources":{"4":source,"5":source}}),
    ])
    await db_session.commit()
    snapshot = await TemporalStateService(db_session).get_world_snapshot("p1",5,include_foreshadowing=False)
    assert {character["name"] for character in snapshot.characters} == {"林玄", "苏璃"}
    assert snapshot.story_time["chapter_time_map"] == {"4":"第七日"}


@pytest.mark.asyncio
async def test_world_state_seed_rejects_unadopted_and_invalidated_slices(db_session):
    await _seed_states(db_session)
    from app.models.novel import Chapter, ChapterVersion
    from app.schemas.world_state import WorldStateSnapshotCreateRequest
    from app.services.world_state_service import WorldStateService
    service = WorldStateService(db_session)
    accepted = await service.create_snapshot("p1",4,WorldStateSnapshotCreateRequest.model_validate({
        "state":{"facts":{"城门":"封锁"}}}))
    chapter = (await db_session.execute(select(Chapter).where(Chapter.chapter_number==4))).scalars().first()
    candidate = ChapterVersion(chapter_id=chapter.id, content="未采用的另一种结局")
    db_session.add(candidate)
    await db_session.flush()
    draft = await service.create_snapshot("p1",4,WorldStateSnapshotCreateRequest.model_validate({
        "source_version_id":candidate.id,"state":{"facts":{"城门":"开放"}}}))
    await db_session.commit()
    assert (await service.seed_for_chapter("p1",5)).source_snapshot_id == accepted.id
    assert (await service.latest_for_chapter("p1",4)).id != draft.id
    assert (await service.seed_for_chapter("p1",4)).state is None
    earlier = (await db_session.execute(select(Chapter).where(Chapter.chapter_number==3))).scalars().first()
    changed = ChapterVersion(chapter_id=earlier.id, content="第3章被作者改写")
    db_session.add(changed)
    await db_session.flush()
    earlier.selected_version_id = changed.id
    earlier.revision_id += 1
    await db_session.commit()
    assert (await service.seed_for_chapter("p1",5)).state is None
    assert await service.latest_for_chapter("p1",4) is None
