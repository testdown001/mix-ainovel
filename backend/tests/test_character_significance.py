"""人物意义层（核心缺陷「事实非意义」，2026-08-01）。

现有管线注入的全是「发生了什么」：CharacterState 的九种类型（位置/情绪/健康/物品/
关系/能力/知识/目标/秘密）、伏笔清单、关系标签、章节摘要——没有任何一项回答
「这件事对这个人**意味着**什么」。于是模型能把事件按正确顺序、不违反设定地写出来，
但「没毛病，也不重要」。

本服务抽取四样**会改变后续行为**的东西：信念变化 / 代价 / 关系质变 / 未言明。

⚠️ 本文件最重要的一条是 `test_brief_forbids_stating_meaning_directly`：
不加约束地注入「意义」，模型会把它当台词或旁白**原句写出来**——那是 AI 小说最典型的
「说破」，比不注入更糟。护栏文案是这个特性成立的前提，不是可选的装饰。
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.models  # noqa: F401  触发全部 mapper 注册
import app.models.user_quota  # noqa: F401  防 mapper KeyError

from app.models.memory_layer import CharacterState
from app.models.novel import NovelProject
from app.services.character_significance_service import (
    CharacterSignificance,
    CharacterSignificanceService,
    SignificanceResult,
)


def _prompts(text="系统提示"):
    return SimpleNamespace(get_prompt=AsyncMock(return_value=text))


def _llm(result):
    return SimpleNamespace(generate_structured=AsyncMock(return_value=result))


def _result():
    return SignificanceResult(characters=[
        CharacterSignificance(
            name="沈青崖",
            belief_shift="不再认为师门是可以退回去的地方",
            cost="失去了唯一愿意为他说话的人",
            relational="开始把师兄当成需要提防的对手，而不是可以背靠的人",
            unspoken="两人都知道那句道歉是假的，但谁都没戳穿",
        ),
    ])


async def _seed_project(session, project_id="p-sig"):
    session.add(NovelProject(id=project_id, user_id=1, title="测试书"))
    await session.flush()


# --------------------------------------------------------------------------
# 写侧
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_creates_row_when_state_missing(db_session):
    """状态行还没写时也要能落库——两个后台任务是并行的，不能假设先后顺序。

    建最小行是安全的：读侧对没有事实字段的行只渲染成「角色名：无特殊状态」。
    """
    await _seed_project(db_session)
    stats = await CharacterSignificanceService().extract_and_store(
        project_id="p-sig", chapter_number=4, chapter_content="正文" * 100,
        character_names=["沈青崖"], session=db_session,
        llm_service=_llm(_result()), prompt_service=_prompts(),
    )
    assert stats == {"stored": 1}

    from sqlalchemy import select
    row = (await db_session.execute(
        select(CharacterState).where(CharacterState.character_name == "沈青崖")
    )).scalars().first()
    assert row.extra["significance"]["belief_shift"].startswith("不再认为师门")
    assert row.extra["significance"]["unspoken"].startswith("两人都知道")


@pytest.mark.asyncio
async def test_extract_merges_into_existing_state_without_wiping_facts(db_session):
    """挂到既有状态行上时，绝不能把事实字段或 extra 里别的键抹掉。"""
    await _seed_project(db_session, "p-sig2")
    db_session.add(CharacterState(
        project_id="p-sig2", character_name="沈青崖", chapter_number=4,
        location="丹阁", emotion="警觉", extra={"other_key": "别处写的"},
    ))
    await db_session.flush()

    await CharacterSignificanceService().extract_and_store(
        project_id="p-sig2", chapter_number=4, chapter_content="正文" * 100,
        character_names=["沈青崖"], session=db_session,
        llm_service=_llm(_result()), prompt_service=_prompts(),
    )

    from sqlalchemy import select
    row = (await db_session.execute(
        select(CharacterState).where(CharacterState.project_id == "p-sig2")
    )).scalars().first()
    assert row.location == "丹阁" and row.emotion == "警觉"    # 事实字段没动
    assert row.extra["other_key"] == "别处写的"                # extra 里别的键还在
    assert "significance" in row.extra


@pytest.mark.asyncio
async def test_empty_significance_entries_are_not_stored(db_session):
    """四项全空的角色不落库——空壳会让读侧渲染出没有内容的条目。"""
    await _seed_project(db_session, "p-sig3")
    stats = await CharacterSignificanceService().extract_and_store(
        project_id="p-sig3", chapter_number=1, chapter_content="正文",
        character_names=["路人"], session=db_session,
        llm_service=_llm(SignificanceResult(characters=[CharacterSignificance(name="路人")])),
        prompt_service=_prompts(),
    )
    assert stats == {"stored": 0}


@pytest.mark.asyncio
async def test_extract_degrades_on_missing_prompt_and_llm_error(db_session):
    await _seed_project(db_session, "p-sig4")
    svc = CharacterSignificanceService()

    stats = await svc.extract_and_store(
        project_id="p-sig4", chapter_number=1, chapter_content="正文",
        character_names=[], session=db_session,
        llm_service=_llm(_result()), prompt_service=_prompts(text=None),
    )
    assert stats == {"skipped": "prompt_missing"}

    boom = SimpleNamespace(generate_structured=AsyncMock(side_effect=RuntimeError("挂了")))
    stats = await svc.extract_and_store(
        project_id="p-sig4", chapter_number=1, chapter_content="正文",
        character_names=[], session=db_session,
        llm_service=boom, prompt_service=_prompts(),
    )
    assert stats["skipped"].startswith("error:")

    stats = await svc.extract_and_store(
        project_id="p-sig4", chapter_number=1, chapter_content="   ",
        character_names=[], session=db_session,
        llm_service=_llm(_result()), prompt_service=_prompts(),
    )
    assert stats == {"skipped": "empty_content"}


# --------------------------------------------------------------------------
# 读侧
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brief_takes_latest_per_character(db_session):
    """同一角色多章都有意义时取最近一次——意义是累积后的当前底色，不是历史流水。"""
    await _seed_project(db_session, "p-read")
    for ch, belief in ((2, "旧的信念"), (5, "新的信念")):
        db_session.add(CharacterState(
            project_id="p-read", character_name="沈青崖", chapter_number=ch,
            extra={"significance": {"belief_shift": belief}},
        ))
    await db_session.flush()

    brief = await CharacterSignificanceService().build_significance_brief(
        project_id="p-read", chapter_number=8, session=db_session,
    )
    assert "新的信念" in brief
    assert "旧的信念" not in brief


@pytest.mark.asyncio
async def test_brief_excludes_current_and_future_chapters(db_session):
    """只能读已定稿章节的意义；本章自己的意义此刻还不存在。"""
    await _seed_project(db_session, "p-future")
    db_session.add(CharacterState(
        project_id="p-future", character_name="沈青崖", chapter_number=9,
        extra={"significance": {"belief_shift": "第9章才有的"}},
    ))
    await db_session.flush()

    assert await CharacterSignificanceService().build_significance_brief(
        project_id="p-future", chapter_number=9, session=db_session,
    ) is None


@pytest.mark.asyncio
async def test_brief_is_none_without_data(db_session):
    await _seed_project(db_session, "p-empty")
    db_session.add(CharacterState(
        project_id="p-empty", character_name="沈青崖", chapter_number=1,
        location="丹阁",  # 只有事实，没有意义
    ))
    await db_session.flush()

    assert await CharacterSignificanceService().build_significance_brief(
        project_id="p-empty", chapter_number=5, session=db_session,
    ) is None


def test_brief_forbids_stating_meaning_directly():
    """⭐ 本特性成立的前提：注入的意义必须带「不得直接写出」的护栏。

    不加约束地把「他不再相信示好是无偿的」注入，模型会把它当台词或旁白原句写出来
    ——那是 AI 小说最典型的「说破」，比不注入更糟。
    """
    brief = CharacterSignificanceService._format_brief({
        "沈青崖": {
            "belief_shift": "不再认为师门可以退回去",
            "unspoken": "两人都知道道歉是假的",
        }
    })
    assert brief is not None
    assert "不再认为师门可以退回去" in brief          # 内容在
    assert "严禁" in brief                            # 护栏在
    assert "选择、反应、迟疑、回避" in brief           # 说明了替代手段
    assert "没说破" in brief                          # 对 unspoken 的额外告诫


def test_brief_skips_characters_without_content():
    assert CharacterSignificanceService._format_brief({"路人": {}}) is None


# --------------------------------------------------------------------------
# 门控与接线
# --------------------------------------------------------------------------

def test_switch_defaults_off():
    from app.services.pipeline_config_service import PipelineConfig
    assert PipelineConfig().enable_character_significance is False


def test_prompt_section_is_registered_with_warning_in_label():
    """段落标题本身就要点明「不得直接写出」——模型读标题的注意力高于正文。"""
    import inspect

    from app.services.prompt_assembly_service import PromptAssemblyService

    src = inspect.getsource(PromptAssemblyService.build_prompt_sections)
    assert "[人物意义层]" in src
    assert "不得直接写出" in src
