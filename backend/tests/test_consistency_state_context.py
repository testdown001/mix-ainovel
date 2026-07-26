"""ConsistencyService._get_check_context 角色状态输入接通回归测试。

历史 bug：_get_check_context 只认 extra["raw_state_text"]，而
MemoryLayerService.update_character_state 从不写该键 → character_state 恒为空，
一致性检查一直在没有角色状态输入的情况下运行。
现改读 CharacterState 结构化字段（位置/情绪/健康/实力/能力变化/目标），
extra["raw_state_text"] 仅作历史数据的兼容回退。
"""
import pytest

import app.models.user_quota  # noqa: F401  防 mapper KeyError
from app.models.memory_layer import CharacterState
from app.services.consistency_service import ConsistencyService


def _make_service(db_session) -> ConsistencyService:
    # _get_check_context 不触及 LLM，llm_service 传 None 即可
    return ConsistencyService(db=db_session, llm_service=None)


def _state(**kwargs) -> CharacterState:
    # CharacterState.id 是纯 BigInteger 主键，sqlite 播种须显式赋 id
    defaults = {"character_id": 1}
    defaults.update(kwargs)
    return CharacterState(**defaults)


@pytest.mark.asyncio
async def test_structured_fields_rendered(db_session):
    """结构化字段（无 raw_state_text）应被拼装进 character_state 文本。"""
    db_session.add(
        _state(
            id=1,
            project_id="p1",
            character_name="林小满",
            chapter_number=3,
            location="青云山",
            emotion="愤怒",
            emotion_intensity=7,
            health_status="injured",
            power_level="金丹期",
            power_changes=["突破至金丹期"],
            current_goals=["寻找师父下落"],
        )
    )
    await db_session.commit()

    context = await _make_service(db_session)._get_check_context(
        "p1", include_foreshadowing=False
    )
    text = context["character_state"]
    assert "林小满" in text
    assert "青云山" in text
    assert "愤怒" in text
    assert "强度7" in text
    assert "injured" in text
    assert "金丹期" in text
    assert "寻找师父下落" in text


@pytest.mark.asyncio
async def test_no_states_yields_empty_without_error(db_session):
    """无角色状态数据：不抛错，character_state 缺省为空串。"""
    context = await _make_service(db_session)._get_check_context(
        "p-empty", include_foreshadowing=False
    )
    assert context.get("character_state", "") == ""


@pytest.mark.asyncio
async def test_raw_state_text_takes_priority(db_session):
    """extra.raw_state_text 存在时优先走兼容路径，不再拼装结构化字段。"""
    db_session.add(
        _state(
            id=2,
            project_id="p2",
            character_name="旧角色",
            chapter_number=1,
            location="旧城",
            extra={"raw_state_text": "旧版原始状态文本"},
        )
    )
    # 同项目另一角色只有结构化字段，两条都应出现（旧实现 break 后会丢弃）
    db_session.add(
        _state(
            id=3,
            project_id="p2",
            character_id=2,
            character_name="新角色",
            chapter_number=2,
            location="新城",
        )
    )
    await db_session.commit()

    context = await _make_service(db_session)._get_check_context(
        "p2", include_foreshadowing=False
    )
    text = context["character_state"]
    assert "旧版原始状态文本" in text
    assert "旧城" not in text  # 兼容路径优先，不重复拼装结构化字段
    assert "新角色" in text
    assert "新城" in text


@pytest.mark.asyncio
async def test_dedupe_keeps_latest_snapshot_per_character(db_session):
    """同一角色多章快照：每角色只取最新一条（章节倒序去重）。"""
    db_session.add(
        _state(id=4, project_id="p3", character_name="甲", chapter_number=1, location="村口")
    )
    db_session.add(
        _state(id=5, project_id="p3", character_name="甲", chapter_number=5, location="王都")
    )
    await db_session.commit()

    context = await _make_service(db_session)._get_check_context(
        "p3", include_foreshadowing=False
    )
    text = context["character_state"]
    assert "王都" in text
    assert "村口" not in text
    assert text.count("甲") == 1
