"""卷级 N 路发散卡片（路线三件套 ② 的后半，2026-08-01）。

`ConceptDivergenceService` 在开书前对世界观发散；本服务是它在**连载中**的对应物：
基于故事实际所处位置（上一卷复盘 + 实际摘要）发散下一卷走向，评分收敛取 Top-K。

最关键的一条断言在 `test_applied_card_flows_into_generation_prompt`：
发散卡片与卷级复盘**落在同一个 replan 槽位**，因此选中即刻通过既有的
`[卷级重规划]` 注入通路对后续生成生效——两半是一个特性，不是两个孤岛。
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.models  # noqa: F401  触发全部 mapper 注册
import app.models.user_quota  # noqa: F401  防 mapper KeyError

from app.models.novel import NovelBlueprint, NovelProject
from app.services.volume_divergence_service import VolumeDivergenceService
from app.services.volume_retrospective_service import VolumeRetrospectiveService

_VOLUMES = [
    {"name": "第一卷·出山", "start_chapter": 1, "end_chapter": 10,
     "arc_goal": "主角离开宗门", "climax_hint": "与师兄决裂",
     "retrospective": {"achieved": "离开宗门并与师兄结盟", "drift": "决裂没发生",
                       "unresolved": ["长老的报复未到"]}},
    {"name": "第二卷·入城", "start_chapter": 11, "end_chapter": 20,
     "arc_goal": "在丹阁站稳脚跟", "climax_hint": "揭破丹阁阴谋"},
]

_CARDS = {
    "cards": [
        {"title": "旧敌成盟", "arc_goal": "与长老结盟对抗丹阁", "climax_hint": "盟约反噬",
         "focus": "写活长老的算盘", "avoid": "重复师门追杀", "hook": "最恨的人成了唯一的靠山"},
        {"title": "自立门户", "arc_goal": "在城南另起炉灶", "climax_hint": "被两家夹击",
         "focus": "资源匮乏的窒息感", "avoid": "开挂速通", "hook": "从零开始的爽感"},
        {"title": "没有目标的废卡", "climax_hint": "x"},  # arc_goal 缺失 → 必须被丢弃
    ]
}

_SCORES = {
    "scores": [
        {"index": 0, "surprise": 9, "continuity": 8, "tension": 8, "comment": "反转扎实"},
        {"index": 1, "surprise": 5, "continuity": 6, "tension": 5, "comment": "偏安全"},
    ]
}


def _service(session, responses):
    """按调用顺序返回 responses 里的原始文本。"""
    svc = VolumeDivergenceService(session)
    svc.llm_service = SimpleNamespace(
        get_llm_response=AsyncMock(side_effect=[json.dumps(r, ensure_ascii=False) for r in responses])
    )
    return svc


async def _seed(session, project_id="p-div", volumes=None):
    session.add(NovelProject(id=project_id, user_id=1, title="测试书"))
    session.add(NovelBlueprint(
        project_id=project_id,
        volumes=[dict(v) for v in (volumes if volumes is not None else _VOLUMES)],
    ))
    await session.flush()


# --------------------------------------------------------------------------
# 发散 + 收敛
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_diverge_returns_scored_top_k(db_session):
    await _seed(db_session)
    svc = _service(db_session, [_CARDS, _SCORES])

    cards = await svc.diverge(project_id="p-div", volume_number=2, user_id=1, n=3, keep=2)

    assert len(cards) == 2
    assert cards[0]["title"] == "旧敌成盟"          # 高分在前
    assert cards[0]["score"] == 25                   # 9+8+8
    assert cards[0]["surprise"] == 9
    assert cards[0]["comment"] == "反转扎实"
    assert all(c["arc_goal"] for c in cards)         # 无目标的废卡已被丢弃


@pytest.mark.asyncio
async def test_cards_without_arc_goal_are_dropped(db_session):
    await _seed(db_session, project_id="p-drop")
    svc = _service(db_session, [_CARDS, _SCORES])

    cards = await svc.diverge(project_id="p-drop", volume_number=2, user_id=1, n=3, keep=5)

    assert len(cards) == 2   # 三张里废掉一张
    assert "没有目标的废卡" not in [c["title"] for c in cards]


@pytest.mark.asyncio
async def test_scoring_failure_falls_back_to_original_order(db_session):
    """评分挂了不能整个特性挂掉——原序返回总比没有强。"""
    await _seed(db_session, project_id="p-scorefail")
    svc = VolumeDivergenceService(db_session)
    svc.llm_service = SimpleNamespace(get_llm_response=AsyncMock(side_effect=[
        json.dumps(_CARDS, ensure_ascii=False),
        RuntimeError("评分模型挂了"),
    ]))

    cards = await svc.diverge(project_id="p-scorefail", volume_number=2, user_id=1)

    assert len(cards) == 2
    assert all(c["score"] == 0 for c in cards)


@pytest.mark.asyncio
async def test_generation_failure_returns_empty(db_session):
    await _seed(db_session, project_id="p-genfail")
    svc = VolumeDivergenceService(db_session)
    svc.llm_service = SimpleNamespace(
        get_llm_response=AsyncMock(side_effect=RuntimeError("发散模型挂了"))
    )

    assert await svc.diverge(project_id="p-genfail", volume_number=2, user_id=1) == []


@pytest.mark.asyncio
async def test_out_of_range_volume_returns_empty_without_llm(db_session):
    await _seed(db_session, project_id="p-range")
    svc = _service(db_session, [_CARDS, _SCORES])

    assert await svc.diverge(project_id="p-range", volume_number=9, user_id=1) == []
    svc.llm_service.get_llm_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_context_includes_previous_volume_retrospective(db_session):
    """发散的依据必须是「实际发生了什么」，而不是当初的规划。"""
    await _seed(db_session, project_id="p-ctx")
    svc = VolumeDivergenceService(db_session)
    context = await svc._build_context("p-ctx", 2)
    rendered = svc._render_context(context)

    assert "离开宗门并与师兄结盟" in rendered   # 复盘的实际达成
    assert "决裂没发生" in rendered             # 复盘的偏差
    assert "长老的报复未到" in rendered         # 遗留线索
    assert "第11-20章" in rendered              # 章节范围不变


# --------------------------------------------------------------------------
# 应用：与卷级复盘共用 replan 槽位
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_card_writes_replan_and_preserves_plan(db_session):
    await _seed(db_session, project_id="p-apply")
    ok = await VolumeDivergenceService(db_session).apply_card(
        project_id="p-apply", volume_number=2,
        card={"title": "旧敌成盟", "arc_goal": "与长老结盟对抗丹阁",
              "climax_hint": "盟约反噬", "focus": "写活长老", "avoid": "重复追杀"},
    )
    assert ok is True

    blueprint = await db_session.get(NovelBlueprint, "p-apply")
    replan = blueprint.volumes[1]["replan"]
    assert replan["status"] == "pending"
    assert replan["source"] == "divergence"       # 可与复盘自动产出区分
    assert replan["arc_goal"] == "与长老结盟对抗丹阁"
    # 原规划保留为历史，不被就地覆盖
    assert blueprint.volumes[1]["arc_goal"] == "在丹阁站稳脚跟"
    assert blueprint.volumes[1]["name"] == "第二卷·入城"


@pytest.mark.asyncio
async def test_apply_unknown_volume_returns_false(db_session):
    await _seed(db_session, project_id="p-applybad")
    assert await VolumeDivergenceService(db_session).apply_card(
        project_id="p-applybad", volume_number=99, card={"arc_goal": "x"},
    ) is False


@pytest.mark.asyncio
async def test_applied_card_flows_into_generation_prompt(db_session):
    """核心断言：选中卡片即刻通过卷级复盘那条读侧通路进入生成提示。

    两半共用 replan 槽位，所以发散是「一个特性的另一半」而非孤岛。
    """
    await _seed(db_session, project_id="p-flow")
    await VolumeDivergenceService(db_session).apply_card(
        project_id="p-flow", volume_number=2,
        card={"title": "旧敌成盟", "arc_goal": "与长老结盟对抗丹阁",
              "climax_hint": "盟约反噬", "focus": "写活长老的算盘", "avoid": "重复追杀"},
    )

    brief = await VolumeRetrospectiveService().build_replan_brief(
        project_id="p-flow", chapter_number=15, session=db_session,
    )
    assert brief is not None
    assert "卷级重规划" in brief
    assert "与长老结盟对抗丹阁" in brief
    assert "写活长老的算盘" in brief

    # 第一卷的章节不受影响
    assert await VolumeRetrospectiveService().build_replan_brief(
        project_id="p-flow", chapter_number=3, session=db_session,
    ) is None


# --------------------------------------------------------------------------
# 路由绑定（历史教训：新函数插错位置会错绑到上一个 @router.*）
# --------------------------------------------------------------------------

def test_volume_routes_are_registered_and_bound_correctly():
    # 查 router 对象而非 app.main：后者导入即 dictConfig 设 propagate=False，
    # 会打坏其它用例的 caplog（见 TODO.md 工作原则）。router 已带 /api/novels 前缀。
    import app.api.routers.novels as novels

    paths = {r.path for r in novels.router.routes if hasattr(r, "path")}
    assert "/api/novels/{project_id}/volumes/{volume_number}/diverge" in paths
    assert "/api/novels/{project_id}/volumes/{volume_number}/diverge/apply" in paths
    assert novels.diverge_volume.__name__ == "diverge_volume"
    assert novels.apply_volume_divergence.__name__ == "apply_volume_divergence"
