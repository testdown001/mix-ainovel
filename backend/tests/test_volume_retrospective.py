"""卷级复盘正式重规划（路线三件套 ②，2026-08-01）。

针对「开环规划」核心缺陷：`NovelBlueprint.volumes` 的分卷规划在蓝图阶段写死一次，
此后永不复盘 —— 故事实际写成什么样（VolumeSummary）与当初规划之间的落差无人过问，
下一卷仍按早已过时的假设推进。本服务是 A1（章级滚动细纲修订）在**卷**这一层的同构体。

覆盖：
- 触发条件（只在卷末、只在有下一卷、只在卷摘要已生成时触发，其余一律跳过且不发 LLM）
- 写回 volumes JSON 的形状（本卷 retrospective + 下一卷 replan(pending)）
- 别处已有的卷字段不被抹掉（JSON 列整体重赋值的经典坑）
- 读侧只对本章所属卷的 pending replan 注入，且全程降级
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.models  # noqa: F401  触发全部 mapper 注册
import app.models.user_quota  # noqa: F401  防 mapper KeyError

from app.models.novel import NovelBlueprint, NovelProject
from app.models.project_memory import VolumeSummary
from app.services.volume_retrospective_service import (
    VolumeReplan,
    VolumeRetrospectiveResult,
    VolumeRetrospectiveService,
)

_VOLUMES = [
    {"name": "第一卷·出山", "start_chapter": 1, "end_chapter": 10,
     "arc_goal": "主角离开宗门", "climax_hint": "与师兄决裂"},
    {"name": "第二卷·入城", "start_chapter": 11, "end_chapter": 20,
     "arc_goal": "在丹阁站稳脚跟", "climax_hint": "揭破丹阁阴谋"},
]


def _llm(result):
    return SimpleNamespace(generate_structured=AsyncMock(return_value=result))


def _prompts(text="系统提示"):
    return SimpleNamespace(get_prompt=AsyncMock(return_value=text))


async def _seed(session, project_id="p-vol", volumes=None, with_summary=True):
    # volumes 挂在 NovelBlueprint（主键即 project_id）上，不是 NovelProject
    session.add(NovelProject(id=project_id, user_id=1, title="测试书"))
    session.add(NovelBlueprint(project_id=project_id, volumes=volumes if volumes is not None else _VOLUMES))
    if with_summary:
        session.add(VolumeSummary(
            project_id=project_id, volume_number=1,
            chapter_start=1, chapter_end=10,
            title="第一卷", summary="主角确实离开了宗门，但没跟师兄决裂，反而联手对付长老。",
            chapter_count=10,
        ))
    await session.flush()


def _result():
    return VolumeRetrospectiveResult(
        achieved="主角离开宗门并与师兄结盟",
        drift="原计划的决裂没有发生，改为联手",
        unresolved=["长老的报复尚未到来"],
        next_volume=VolumeReplan(
            arc_goal="带着师兄这个盟友在丹阁立足",
            climax_hint="盟友身份暴露引发丹阁清算",
            focus="把师兄从工具人写成有自己算盘的人",
            avoid="再写一次师门追杀",
        ),
    )


# --------------------------------------------------------------------------
# 触发条件
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reviews_at_volume_end(db_session):
    await _seed(db_session)
    llm = _llm(_result())

    stats = await VolumeRetrospectiveService().review_volume(
        project_id="p-vol", finalized_chapter_number=10,
        session=db_session, llm_service=llm, prompt_service=_prompts(),
    )

    assert stats["reviewed"] is True
    assert stats["replanned_volume"] == 2
    llm.generate_structured.assert_awaited_once()


@pytest.mark.asyncio
async def test_skips_mid_volume_chapter(db_session):
    """卷内每章都复盘既贵又没有新信息——非卷末一律不发 LLM。"""
    await _seed(db_session, project_id="p-mid")
    llm = _llm(_result())

    stats = await VolumeRetrospectiveService().review_volume(
        project_id="p-mid", finalized_chapter_number=7,
        session=db_session, llm_service=llm, prompt_service=_prompts(),
    )

    assert stats == {"skipped": "not_volume_end"}
    llm.generate_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_skips_last_volume(db_session):
    """最后一卷没有下一卷可重规划。"""
    await _seed(db_session, project_id="p-last")
    db_session.add(VolumeSummary(
        project_id="p-last", volume_number=2, chapter_start=11, chapter_end=20,
        summary="第二卷摘要", chapter_count=10,
    ))
    await db_session.flush()
    llm = _llm(_result())

    stats = await VolumeRetrospectiveService().review_volume(
        project_id="p-last", finalized_chapter_number=20,
        session=db_session, llm_service=llm, prompt_service=_prompts(),
    )

    assert stats == {"skipped": "last_volume"}
    llm.generate_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_skips_when_volume_summary_missing(db_session):
    """没有「实际写成什么」就无从对比，不能拿空摘要去问 LLM。"""
    await _seed(db_session, project_id="p-nosum", with_summary=False)
    llm = _llm(_result())

    stats = await VolumeRetrospectiveService().review_volume(
        project_id="p-nosum", finalized_chapter_number=10,
        session=db_session, llm_service=llm, prompt_service=_prompts(),
    )

    assert stats == {"skipped": "no_volume_summary"}
    llm.generate_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_skips_when_no_volumes(db_session):
    await _seed(db_session, project_id="p-novol", volumes=[], with_summary=False)
    stats = await VolumeRetrospectiveService().review_volume(
        project_id="p-novol", finalized_chapter_number=10,
        session=db_session, llm_service=_llm(_result()), prompt_service=_prompts(),
    )
    assert stats == {"skipped": "no_volumes"}


@pytest.mark.asyncio
async def test_missing_prompt_degrades_silently(db_session):
    await _seed(db_session, project_id="p-noprompt")
    stats = await VolumeRetrospectiveService().review_volume(
        project_id="p-noprompt", finalized_chapter_number=10,
        session=db_session, llm_service=_llm(_result()),
        prompt_service=_prompts(text=None),
    )
    assert stats == {"skipped": "llm_failed"}


@pytest.mark.asyncio
async def test_llm_exception_does_not_propagate(db_session):
    """复盘失败绝不能把定稿流程带崩。"""
    await _seed(db_session, project_id="p-boom")
    llm = SimpleNamespace(generate_structured=AsyncMock(side_effect=RuntimeError("LLM 挂了")))

    stats = await VolumeRetrospectiveService().review_volume(
        project_id="p-boom", finalized_chapter_number=10,
        session=db_session, llm_service=llm, prompt_service=_prompts(),
    )
    assert stats == {"skipped": "llm_failed"}


# --------------------------------------------------------------------------
# 写回形状
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_writes_retrospective_and_replan_shapes(db_session):
    await _seed(db_session, project_id="p-shape")
    await VolumeRetrospectiveService().review_volume(
        project_id="p-shape", finalized_chapter_number=10,
        session=db_session, llm_service=_llm(_result()), prompt_service=_prompts(),
    )

    project = await db_session.get(NovelBlueprint, "p-shape")
    retro = project.volumes[0]["retrospective"]
    assert retro["drift"].startswith("原计划的决裂没有发生")
    assert retro["unresolved"] == ["长老的报复尚未到来"]
    assert retro["source_chapter"] == 10

    replan = project.volumes[1]["replan"]
    assert replan["status"] == "pending"
    assert replan["focus"].startswith("把师兄")
    assert replan["avoid"] == "再写一次师门追杀"


@pytest.mark.asyncio
async def test_existing_volume_fields_are_preserved(db_session):
    """JSON 列整体重赋值的经典坑：别把卷上别处写入的字段一起抹了。"""
    volumes = [dict(v) for v in _VOLUMES]
    volumes[1]["author_note"] = "作者手写的备注"
    await _seed(db_session, project_id="p-keep", volumes=volumes)

    await VolumeRetrospectiveService().review_volume(
        project_id="p-keep", finalized_chapter_number=10,
        session=db_session, llm_service=_llm(_result()), prompt_service=_prompts(),
    )

    project = await db_session.get(NovelBlueprint, "p-keep")
    assert project.volumes[1]["author_note"] == "作者手写的备注"
    assert project.volumes[1]["name"] == "第二卷·入城"        # 原规划字段仍在
    assert project.volumes[1]["arc_goal"] == "在丹阁站稳脚跟"  # 原规划不被就地覆盖
    assert project.volumes[1]["replan"]["arc_goal"] != project.volumes[1]["arc_goal"]


# --------------------------------------------------------------------------
# 读侧
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_side_injects_only_for_owning_volume(db_session):
    volumes = [dict(v) for v in _VOLUMES]
    volumes[1]["replan"] = {
        "arc_goal": "带着盟友立足", "climax_hint": "身份暴露",
        "focus": "写活师兄", "avoid": "重复追杀", "status": "pending",
    }
    await _seed(db_session, project_id="p-read", volumes=volumes, with_summary=False)
    svc = VolumeRetrospectiveService()

    brief = await svc.build_replan_brief(project_id="p-read", chapter_number=13, session=db_session)
    assert brief is not None
    assert "卷级重规划" in brief
    assert "写活师兄" in brief

    # 第一卷的章节不该拿到第二卷的重规划
    assert await svc.build_replan_brief(
        project_id="p-read", chapter_number=3, session=db_session,
    ) is None
    # 落在任何卷之外的章号同样不注入
    assert await svc.build_replan_brief(
        project_id="p-read", chapter_number=99, session=db_session,
    ) is None


@pytest.mark.asyncio
async def test_read_side_ignores_non_pending_replan(db_session):
    volumes = [dict(v) for v in _VOLUMES]
    volumes[1]["replan"] = {"arc_goal": "旧的", "status": "superseded"}
    await _seed(db_session, project_id="p-stale", volumes=volumes, with_summary=False)

    assert await VolumeRetrospectiveService().build_replan_brief(
        project_id="p-stale", chapter_number=13, session=db_session,
    ) is None


@pytest.mark.asyncio
async def test_read_side_returns_none_for_unknown_project(db_session):
    assert await VolumeRetrospectiveService().build_replan_brief(
        project_id="不存在", chapter_number=1, session=db_session,
    ) is None


def test_malformed_volume_entries_are_ignored():
    """章号非法/结构不对的卷条目一律丢弃，口径与 writer._build_volume_context 一致。"""
    project = SimpleNamespace(volumes=[
        "不是字典",
        {"start_chapter": "x", "end_chapter": 5},
        {"start_chapter": 8, "end_chapter": 3},      # end < start
        {"start_chapter": 0, "end_chapter": 5},      # start <= 0
        {"start_chapter": 1, "end_chapter": 5, "name": "好的"},
    ])
    parsed = VolumeRetrospectiveService._parse_volumes(project)
    assert len(parsed) == 1 and parsed[0]["name"] == "好的"
