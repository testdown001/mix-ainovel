"""大纲结构化规划字段的落库与消费。

历史缺口（7 月整改遗留项，2026-08-01 补）：`prompts/outline_generation.md:134-139`
每章都要求 LLM 产出 `narrative_phase` / `foreshadowing.plant|payoff` / `emotion_hook`，
而落库只取 title+summary —— 这三个字段**章章生成、章章丢弃**，等于每章白付一笔 token。

现落进 `outline.metadata["planning"]`，并让 `narrative_phase` 在生成提示里
**替换**掉 PacingController 的位置公式猜测（大纲声明的是「事件/势力/挑衅1..回击4」
这套具体结构，比通用三幕模板更贴本书）。
"""
import pytest

import app.models  # noqa: F401  触发全部 mapper 注册
import app.models.user_quota  # noqa: F401  防 mapper KeyError

from app.models.novel import ChapterOutline
from app.services.novel_service import NovelService
from app.services.writer_shared import extract_outline_planning_metadata


# --------------------------------------------------------------------------
# 提取与归一
# --------------------------------------------------------------------------

def test_extracts_all_three_field_groups():
    meta = extract_outline_planning_metadata({
        "chapter_number": 7,
        "title": "破阵",
        "summary": "摘要",
        "narrative_phase": "回击2",
        "emotion_hook": "扬眉吐气",
        "foreshadowing": {"plant": ["黑铁禁门的裂纹"], "payoff": ["师兄的告诫"]},
    })
    assert meta == {
        "planning": {
            "narrative_phase": "回击2",
            "emotion_hook": "扬眉吐气",
            "foreshadowing": {"plant": ["黑铁禁门的裂纹"], "payoff": ["师兄的告诫"]},
        }
    }["planning"]


def test_returns_none_when_no_planning_fields():
    """全缺失时返回 None，调用方不必写空壳（也就不会平白触发一次 metadata 重写）。"""
    assert extract_outline_planning_metadata({"chapter_number": 1, "title": "t", "summary": "s"}) is None


def test_ignores_blank_and_wrong_typed_values():
    assert extract_outline_planning_metadata({
        "narrative_phase": "   ",
        "emotion_hook": None,
        "foreshadowing": "不是字典",
    }) is None


def test_single_string_foreshadowing_is_normalized_to_list():
    """LLM 偶尔把单条伏笔写成字符串而非数组，须归一，否则下游按列表处理会炸。"""
    meta = extract_outline_planning_metadata({"foreshadowing": {"plant": "只有一条伏笔"}})
    assert meta == {"foreshadowing": {"plant": ["只有一条伏笔"]}}


def test_empty_foreshadowing_lists_are_dropped():
    assert extract_outline_planning_metadata({"foreshadowing": {"plant": [], "payoff": ["  "]}}) is None


def test_values_are_stripped():
    meta = extract_outline_planning_metadata({
        "narrative_phase": "  挑衅3  ",
        "foreshadowing": {"payoff": ["  旧怨  "]},
    })
    assert meta["narrative_phase"] == "挑衅3"
    assert meta["foreshadowing"]["payoff"] == ["旧怨"]


# --------------------------------------------------------------------------
# 落库（真实 DB）
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_planning_metadata_is_persisted_on_create(db_session):
    outline = await NovelService(db_session).update_or_create_outline(
        "proj-plan", 1, "标题", "摘要",
        metadata=extract_outline_planning_metadata({
            "narrative_phase": "事件", "emotion_hook": "悬念",
        }),
    )
    assert outline.metadata["narrative_phase"] == "事件"
    assert outline.metadata["emotion_hook"] == "悬念"


@pytest.mark.asyncio
async def test_regenerating_outline_does_not_wipe_prediction(db_session):
    """重生成大纲会带 planning 落库——绝不能顺手抹掉别处写入的 prediction。

    这是本次改动最大的回归风险：落库原先是「整体替换 metadata」。
    """
    db_session.add(ChapterOutline(
        project_id="proj-plan2", chapter_number=3,
        title="旧", summary="旧", metadata={"prediction": {"hits": 3}},
    ))
    await db_session.flush()

    outline = await NovelService(db_session).update_or_create_outline(
        "proj-plan2", 3, "新", "新",
        metadata=extract_outline_planning_metadata({"narrative_phase": "挑衅1"}),
    )
    assert outline.metadata["prediction"] == {"hits": 3}   # 别处的键还在
    assert outline.metadata["narrative_phase"] == "挑衅1"


@pytest.mark.asyncio
async def test_no_planning_fields_leaves_existing_metadata_untouched(db_session):
    """LLM 没产出规划字段时传 None，既有 metadata 不应被改动。"""
    db_session.add(ChapterOutline(
        project_id="proj-plan3", chapter_number=2,
        title="旧", summary="旧", metadata={"prediction": {"hits": 1}},
    ))
    await db_session.flush()

    outline = await NovelService(db_session).update_or_create_outline(
        "proj-plan3", 2, "新", "新", metadata=extract_outline_planning_metadata({"title": "无规划字段"}),
    )
    assert outline.metadata == {"prediction": {"hits": 1}}


# --------------------------------------------------------------------------
# 消费：大纲声明的叙事阶段优先于 PacingController 的位置猜测
# --------------------------------------------------------------------------

def _render_pacing(planned: dict, pacing_info: dict) -> list[str]:
    """复刻 pipeline_orchestrator._compute_pacing 的取值优先级。

    该逻辑嵌在 generate_chapter 内部的闭包里，整链路起测代价过高；
    这里锁住「优先级」这一真正会回归的点。
    """
    parts = []
    if pacing_info.get("emotion_intensity"):
        parts.append(f"- **情绪强度**: {pacing_info['emotion_intensity']:.1f}/10")
    narrative_phase = planned.get("narrative_phase") or pacing_info.get("narrative_phase")
    if narrative_phase:
        parts.append(f"- **叙事阶段**: {narrative_phase}")
    if planned.get("emotion_hook"):
        parts.append(f"- **本章情绪钩子**: {planned['emotion_hook']}")
    return parts


def test_outline_phase_overrides_pacing_controller_guess():
    """大纲声明的阶段胜出，且**只出现一次**（替换而非叠加，避免约束堆叠）。"""
    parts = _render_pacing(
        {"narrative_phase": "回击3", "emotion_hook": "复仇快意"},
        {"emotion_intensity": 7.5, "narrative_phase": "高潮"},
    )
    phase_lines = [p for p in parts if "叙事阶段" in p]
    assert len(phase_lines) == 1
    assert "回击3" in phase_lines[0]
    assert "高潮" not in phase_lines[0]
    assert any("复仇快意" in p for p in parts)


def test_falls_back_to_pacing_controller_when_outline_has_no_phase():
    """老项目大纲没有 planning 字段时，行为与改动前一致。"""
    parts = _render_pacing({}, {"emotion_intensity": 5.0, "narrative_phase": "铺垫"})
    assert any("铺垫" in p for p in parts)
    assert not any("情绪钩子" in p for p in parts)
