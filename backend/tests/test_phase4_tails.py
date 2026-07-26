"""W5 小尾巴收口测试。

覆盖：
1. 伏笔 overdue 阈值随总章数缩放：max(20, total//5)，拿不到 total 降级基线 20
   （foreshadowing_tracker_service.get_foreshadowings_for_chapter +
     platinum_writing_context._score_foreshadowing / build_foreshadowing_urgency_brief）
2. regenerate 两处全量大纲注入治理：近 20 章全量 + 更早仅标题（writer._governed_outline_lines）
3. memory_layer 模型主键 sqlite 变体：无显式 id 插入自增成功，显式 id 仍兼容
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.models  # noqa: F401  mapper 注册
import app.models.user_quota  # noqa: F401

from app.api.routers import writer as writer_module
from app.models.foreshadowing import Foreshadowing
from app.models.memory_layer import (
    CausalChain,
    CharacterState,
    StoryTimeTracker,
    TimelineEvent,
)
from app.models.novel import ChapterOutline
from app.services.foreshadowing_tracker_service import ForeshadowingTrackerService
from app.services.platinum_writing_context import (
    _score_foreshadowing,
    build_foreshadowing_urgency_brief,
    overdue_age_threshold,
    resolve_total_chapters,
)


# ---------------------------------------------------------------------------
# 1. overdue 阈值缩放
# ---------------------------------------------------------------------------

def test_overdue_threshold_scales_with_total_chapters():
    assert overdue_age_threshold(300) == 60
    assert overdue_age_threshold(150) == 30
    # 短篇/拿不到 total：保持基线 20（现行为）
    assert overdue_age_threshold(80) == 20
    assert overdue_age_threshold(None) == 20
    assert overdue_age_threshold(0) == 20


def _fs_ns(planted_chapter):
    return SimpleNamespace(
        id=1,
        urgency=0,
        importance=None,
        target_reveal_chapter=None,
        chapter_number=planted_chapter,
        name="旧伏笔",
        content="内容",
    )


def test_score_foreshadowing_age_bonus_scaled():
    item = _fs_ns(1)
    # 300 章项目：第 30 章时 age=29 < 60，不触发「读者记忆风险」加分
    score_scaled, reasons_scaled = _score_foreshadowing(item, 30, total_chapters=300)
    assert not any("读者记忆风险" in r for r in reasons_scaled)
    # 无 total（现行为）：age=29 >= 20 触发
    score_base, reasons_base = _score_foreshadowing(item, 30)
    assert any("读者记忆风险" in r for r in reasons_base)
    assert score_base == score_scaled + 4 - 2  # 基线 +4；缩放侧落入 age>=10 档 +2


def test_resolve_total_chapters_degrades_on_error():
    session = SimpleNamespace(execute=AsyncMock(side_effect=RuntimeError("db down")))
    assert asyncio.run(resolve_total_chapters(session, "p1")) is None


@pytest.mark.asyncio
async def test_tracker_overdue_threshold_scaled_by_outline_count(db_session):
    # 300 章项目：阈值 60；埋设 29 章不再判 overdue
    db_session.add_all(
        ChapterOutline(project_id="p300", chapter_number=i, title=f"T{i}")
        for i in range(1, 301)
    )
    db_session.add(
        Foreshadowing(
            project_id="p300", chapter_id=1, chapter_number=1,
            content="三百章项目的旧伏笔", type="hint", status="planted",
        )
    )
    # 无大纲项目：降级基线 20；埋设 29 章仍判 overdue（现行为不变）
    db_session.add(
        Foreshadowing(
            project_id="p-none", chapter_id=1, chapter_number=1,
            content="无大纲项目的旧伏笔", type="hint", status="planted",
        )
    )
    await db_session.commit()

    tracker = ForeshadowingTrackerService(db_session)

    scaled = await tracker.get_foreshadowings_for_chapter("p300", 30)
    assert not scaled["overdue"]
    assert len(scaled["related"]) == 1

    base = await tracker.get_foreshadowings_for_chapter("p-none", 30)
    assert len(base["overdue"]) == 1

    # 显式传 total_chapters 时优先生效（穿透口）
    forced = await tracker.get_foreshadowings_for_chapter("p300", 30, total_chapters=100)
    assert len(forced["overdue"]) == 1


@pytest.mark.asyncio
async def test_urgency_brief_uses_scaled_threshold(db_session):
    db_session.add_all(
        ChapterOutline(project_id="p300", chapter_number=i, title=f"T{i}")
        for i in range(1, 301)
    )
    db_session.add(
        Foreshadowing(
            project_id="p300", chapter_id=1, chapter_number=1,
            content="三百章项目的旧伏笔", type="hint", status="planted", name="旧伏笔",
        )
    )
    db_session.add(
        Foreshadowing(
            project_id="p-none", chapter_id=1, chapter_number=1,
            content="无大纲项目的旧伏笔", type="hint", status="planted", name="旧伏笔",
        )
    )
    await db_session.commit()

    scaled_brief = await build_foreshadowing_urgency_brief(
        session=db_session, project_id="p300", chapter_number=30
    )
    assert "读者记忆风险" not in scaled_brief

    base_brief = await build_foreshadowing_urgency_brief(
        session=db_session, project_id="p-none", chapter_number=30
    )
    assert "读者记忆风险" in base_brief


# ---------------------------------------------------------------------------
# 2. regenerate 大纲注入治理：近 20 全量 + 远章标题
# ---------------------------------------------------------------------------

def _make_outline(num):
    return SimpleNamespace(chapter_number=num, title=f"T{num:03d}", summary=f"O{num:03d}大纲内容")


def test_regenerate_outline_lines_governed_for_long_project():
    """300 章项目：仅最近 20 章保留完整大纲，更早 280 章仅剩标题行。"""
    outlines = [_make_outline(i) for i in range(1, 301)]
    lines = writer_module._governed_outline_lines(outlines)
    text = "\n".join(lines)

    # 近 20 章（281-300）全量
    assert "O281大纲内容" in text
    assert "O300大纲内容" in text
    # 更早章节只剩标题
    assert "O100大纲内容" not in text
    assert "O280大纲内容" not in text
    assert "第100章 - T100" in text
    assert "仅列出标题" in text
    # 1 行说明 + 280 行标题 + 20 行全量
    assert len(lines) == 301


def test_regenerate_outline_lines_small_project_unchanged():
    outlines = [_make_outline(i) for i in range(1, 11)]
    lines = writer_module._governed_outline_lines(outlines)
    assert len(lines) == 10
    assert all("大纲内容" in line for line in lines)


# ---------------------------------------------------------------------------
# 3. memory_layer 主键 sqlite 变体：无显式 id 自增插入成功
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_layer_autoincrement_on_sqlite(db_session):
    rows = [
        CharacterState(project_id="p1", character_id=1, character_name="林战", chapter_number=1),
        TimelineEvent(project_id="p1", chapter_number=1, event_title="开局", story_time="第三天早上"),
        CausalChain(project_id="p1", cause_description="因", cause_chapter=1, effect_description="果"),
        StoryTimeTracker(project_id="p1"),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    for row in rows:
        assert row.id is not None and row.id > 0

    # 既有测试显式赋 id 的播种方式仍兼容
    explicit = TimelineEvent(
        id=999, project_id="p1", chapter_number=2, event_title="显式ID", story_time="当晚"
    )
    db_session.add(explicit)
    await db_session.commit()
    assert explicit.id == 999
