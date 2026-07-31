"""CharacterState 真实落库回归测试。

历史 bug（2026-07-31 服务器实跑基线时从日志揪出）：
`character_states.character_id` 曾是 NOT NULL，而唯一写入方
`MemoryLayerService.update_character_state` 并不接收 character_id，只能从"上一条
状态"继承 —— 上一条状态又必须写成功才存在。首次写必为 NULL → IntegrityError
→ 永远 bootstrap 不了，角色状态在生产上 100% 从未落库。
连带：失败的 flush 让共享 session 停在待回滚态，紧随其后的时间线写入必然报
PendingRollbackError，两者总是同时丢。

原有测试（test_state_tracking_downshift.py）把 update_character_state 整个
AsyncMock 掉，只验证"是否被调用"，从不碰真实写入，因此漏掉了这个必然失败的
INSERT。本文件刻意走真实 DB 写入。
"""
import pytest
from sqlalchemy import select

import app.models.user_quota  # noqa: F401  防 mapper KeyError
from app.models.memory_layer import CharacterState, TimelineEvent
from app.services.memory_layer_service import MemoryLayerService


def _service(db_session) -> MemoryLayerService:
    # 本文件只测 DB 写入路径，不触 LLM/mem0
    return MemoryLayerService(db=db_session, llm_service=None, prompt_service=None)


@pytest.mark.asyncio
async def test_first_write_without_character_id_persists(db_session):
    """无 character_id 且无历史状态时，首次写入必须成功落库（原来必抛 IntegrityError）。"""
    svc = _service(db_session)

    state = await svc.update_character_state(
        project_id="p1",
        character_name="沈青崖",
        chapter_number=4,
        state_updates={"location": "丹阁", "emotion": "隐忍"},
    )

    assert state.id is not None
    assert state.character_id is None  # 抽取出的角色不在蓝图角色表里，允许为空
    rows = (
        await db_session.execute(
            select(CharacterState).where(CharacterState.project_id == "p1")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].character_name == "沈青崖"
    assert rows[0].location == "丹阁"


@pytest.mark.asyncio
async def test_second_chapter_inherits_previous_state(db_session):
    """第二章应继承上一章状态，且不因 character_id 为空而失败。"""
    svc = _service(db_session)
    await svc.update_character_state(
        project_id="p1",
        character_name="沈青崖",
        chapter_number=4,
        state_updates={"location": "丹阁", "health_status": "injured"},
    )

    later = await svc.update_character_state(
        project_id="p1",
        character_name="沈青崖",
        chapter_number=5,
        state_updates={"emotion": "决然"},
    )

    assert later.location == "丹阁"          # 继承
    assert later.health_status == "injured"  # 继承
    assert later.emotion == "决然"           # 本章更新


@pytest.mark.asyncio
async def test_explicit_character_id_is_kept(db_session):
    """显式传入 character_id 时照常保留（不因放开可空而丢关联）。"""
    svc = _service(db_session)
    state = await svc.update_character_state(
        project_id="p1",
        character_name="焚寂",
        chapter_number=1,
        state_updates={},
        character_id=42,
    )
    assert state.character_id == 42


@pytest.mark.asyncio
async def test_state_failure_does_not_take_down_timeline(db_session, monkeypatch):
    """步骤 1 写角色状态失败后，步骤 2 时间线仍须能写入（session 已复位）。

    这是线上"角色状态与时间线总是同时丢"的连带伤害，靠 _safe_rollback 阻断。
    """
    svc = _service(db_session)

    async def _boom(*args, **kwargs):
        # 制造一次真实的 flush 失败：非空列写 None
        db_session.add(CharacterState(project_id=None, character_name="x", chapter_number=1))
        await db_session.commit()

    monkeypatch.setattr(svc, "update_character_state", _boom)
    monkeypatch.setattr(
        svc, "extract_character_states_from_chapter",
        lambda *a, **k: _async_value([{"character_name": "沈青崖", "location": "丹阁"}]),
    )
    monkeypatch.setattr(
        svc, "extract_timeline_events_from_chapter",
        lambda *a, **k: _async_value(
            [{"event_title": "丹阁风波", "event_description": "调包栽赃被识破"}]
        ),
    )

    results = await svc.update_state_after_chapter(
        project_id="p1",
        chapter_number=4,
        chapter_content="正文",
        character_names=["沈青崖"],
        user_id=1,
    )

    assert results["character_states_updated"] == 0  # 步骤 1 如实失败
    events = (
        await db_session.execute(
            select(TimelineEvent).where(TimelineEvent.project_id == "p1")
        )
    ).scalars().all()
    assert len(events) == 1  # 步骤 2 未被连累
    assert results["timeline_events_added"] == 1


async def _async_value(value):
    return value
