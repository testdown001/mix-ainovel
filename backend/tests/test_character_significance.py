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
from app.models.novel import NovelProject, Chapter, ChapterVersion
from app.services.character_significance_service import (
    CharacterSignificance,
    CharacterSignificanceService,
    SignificanceResult,
    SignificanceMemory,
)

_CHAPTER_TEXT = "沈青崖将师门令牌留在桌上。他没有接师兄递来的信。"


async def _seed_chapter(session, project_id, number, content):
    chapter = Chapter(project_id=project_id, chapter_number=number)
    session.add(chapter)
    await session.flush()
    version = ChapterVersion(chapter_id=chapter.id, content=content)
    session.add(version)
    await session.flush()
    chapter.selected_version_id = version.id
    await session.commit()
    return chapter, version


def _prompts(text="系统提示"):
    return SimpleNamespace(get_prompt=AsyncMock(return_value=text))


def _llm(result):
    return SimpleNamespace(generate_structured=AsyncMock(return_value=result))


def _result():
    return SignificanceResult(characters=[
        CharacterSignificance(
            name="沈青崖",
            memories=[
                SignificanceMemory(kind="belief_shift", meaning="不再认为师门是可以退回去的地方", evidence="沈青崖将师门令牌留在桌上"),
                SignificanceMemory(kind="unspoken", meaning="两人都知道信任已经动摇", evidence="他没有接师兄递来的信", related_characters=["师兄"]),
            ],
            belief_shift="不再认为师门是可以退回去的地方",
            cost="失去了唯一愿意为他说话的人",
            relational="开始把师兄当成需要提防的对手，而不是可以背靠的人",
            unspoken="两人都知道那句道歉是假的，但谁都没戳穿",
        ),
    ])


async def _seed_project(session, project_id="p-sig"):
    session.add(NovelProject(id=project_id, user_id=1, title="测试书"))
    await session.flush()
    await _seed_chapter(session, project_id, 1, "正文")
    await _seed_chapter(session, project_id, 4, _CHAPTER_TEXT)


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
        project_id="p-sig", chapter_number=4, chapter_content=_CHAPTER_TEXT,
        character_names=["沈青崖"], session=db_session,
        llm_service=_llm(_result()), prompt_service=_prompts(),
    )
    assert stats == {"stored": 1}

    from sqlalchemy import select
    row = (await db_session.execute(
        select(CharacterState).where(CharacterState.character_name == "沈青崖")
    )).scalars().first()
    ledger = row.extra["significance_v2"]
    assert ledger["source"]["version_id"]
    assert ledger["events"][0]["meaning"].startswith("不再认为师门")
    assert ledger["events"][1]["meaning"].startswith("两人都知道")


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
        project_id="p-sig2", chapter_number=4, chapter_content=_CHAPTER_TEXT,
        character_names=["沈青崖"], session=db_session,
        llm_service=_llm(_result()), prompt_service=_prompts(),
    )

    from sqlalchemy import select
    row = (await db_session.execute(
        select(CharacterState).where(CharacterState.project_id == "p-sig2")
    )).scalars().first()
    assert row.location == "丹阁" and row.emotion == "警觉"    # 事实字段没动
    assert row.extra["other_key"] == "别处写的"                # extra 里别的键还在
    assert "significance_v2" in row.extra


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
    """旧数据只能按同一字段取最近记录，不覆盖人物的其他心结。"""
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

@pytest.mark.asyncio
async def test_unresolved_memories_survive_new_changes_and_explicit_resolution(db_session):
    await _seed_project(db_session, "p-long")
    svc = CharacterSignificanceService()
    old_text = "沈青崖拒绝把后背交给师兄，独自守在门口。"
    new_text = "沈青崖接过旅人的水袋，第一次向陌生人道了谢。"
    end_text = "沈青崖把背后交给师兄，点头说旧账到这里算清了。"
    async def store(number, text, memory):
        await _seed_chapter(db_session, "p-long", number, text)
        return await svc.extract_and_store(
            project_id="p-long", chapter_number=number, chapter_content=text,
            character_names=["沈青崖"], session=db_session,
            llm_service=_llm(SignificanceResult(characters=[CharacterSignificance(name="沈青崖", memories=[memory])])),
            prompt_service=_prompts(),
        )
    await store(12, old_text, SignificanceMemory(kind="unspoken", meaning="无法原谅师兄的背叛",
                evidence="沈青崖拒绝把后背交给师兄", trigger="与师兄并肩作战", related_characters=["师兄"]))
    await store(13, new_text, SignificanceMemory(kind="belief_shift", meaning="愿意接受陌生人的帮助",
                evidence="第一次向陌生人道了谢"))
    brief = await svc.build_significance_brief(project_id="p-long", chapter_number=14,
                involved_characters=["沈青崖", "师兄"], chapter_context="与师兄并肩作战", session=db_session)
    assert "无法原谅师兄的背叛" in brief and "愿意接受陌生人的帮助" in brief
    assert "第12章" in brief and "原文依据" in brief
    records = await svc._active_memories(db_session, "p-long", 14)
    old_id = next(m["id"] for m in records if m["kind"] == "unspoken")
    await store(15, end_text, SignificanceMemory(kind="unspoken", meaning="旧账已化解", action="resolve",
                target_id=old_id, evidence="点头说旧账到这里算清了"))
    before = await svc.build_significance_brief(project_id="p-long", chapter_number=15, session=db_session)
    after = await svc.build_significance_brief(project_id="p-long", chapter_number=16, session=db_session)
    assert "无法原谅" in before and "无法原谅" not in after
    assert "愿意接受" in after
    from sqlalchemy import select
    resolution_chapter = (await db_session.execute(select(Chapter).where(
        Chapter.project_id == "p-long", Chapter.chapter_number == 15))).scalars().first()
    replacement = ChapterVersion(chapter_id=resolution_chapter.id, content="沈青崖依旧独自守门。")
    db_session.add(replacement)
    await db_session.flush()
    resolution_chapter.selected_version_id = replacement.id
    await db_session.commit()
    reverted = await svc.build_significance_brief(project_id="p-long", chapter_number=16, session=db_session)
    assert "无法原谅" in reverted  # 删除和解情节后，旧心结恢复，不能继续误用旧版化解。


@pytest.mark.asyncio
async def test_unselected_or_changed_source_never_becomes_memory(db_session):
    await _seed_project(db_session, "p-source")
    svc = CharacterSignificanceService()
    llm = _llm(_result())
    stats = await svc.extract_and_store(project_id="p-source", chapter_number=4, chapter_content="未采用版本",
        character_names=["沈青崖"], session=db_session, llm_service=llm, prompt_service=_prompts())
    assert stats["skipped"] == "not_current_selected_version"
    llm.generate_structured.assert_not_called()
    args = dict(project_id="p-source", chapter_number=4, chapter_content=_CHAPTER_TEXT,
        character_names=["沈青崖"], session=db_session, llm_service=llm, prompt_service=_prompts())
    assert (await svc.extract_and_store(**args))["stored"] == 1
    assert (await svc.extract_and_store(**args))["skipped"] == "already_extracted"
    from sqlalchemy import select
    chapter = (await db_session.execute(select(Chapter).where(
        Chapter.project_id == "p-source", Chapter.chapter_number == 4))).scalars().first()
    revision = ChapterVersion(chapter_id=chapter.id, content="沈青崖和师兄言归于好。")
    db_session.add(revision)
    await db_session.flush()
    chapter.selected_version_id = revision.id
    await db_session.commit()
    assert await svc.build_significance_brief(project_id="p-source", chapter_number=5, session=db_session) is None


@pytest.mark.asyncio
async def test_invented_evidence_and_wrong_target_are_rejected(db_session):
    await _seed_project(db_session, "p-proof")
    svc = CharacterSignificanceService()
    result = SignificanceResult(characters=[CharacterSignificance(name="沈青崖", memories=[
        SignificanceMemory(kind="cost", meaning="失去了师妹", evidence="师妹死在雪地里"),
        SignificanceMemory(kind="unspoken", meaning="原谅师兄", evidence="他没有接师兄递来的信",
                           action="resolve", target_id="invented"),
    ])])
    stats = await svc.extract_and_store(project_id="p-proof", chapter_number=4, chapter_content=_CHAPTER_TEXT,
        character_names=["沈青崖"], session=db_session, llm_service=_llm(result), prompt_service=_prompts())
    assert stats == {"stored": 0}
    assert await svc.build_significance_brief(project_id="p-proof", chapter_number=5, session=db_session) is None


def test_relevance_prefers_old_trigger_over_unrelated_recent_changes():
    memories = [
        {"name": "甲", "chapter": 12, "trigger": "师兄", "related_characters": ["师兄"], "meaning": "旧心结"},
        {"name": "甲", "chapter": 40, "trigger": "陌生人", "meaning": "新变化"},
    ]
    ranked = CharacterSignificanceService._rank(memories, ["甲", "师兄"], "甲与师兄共同行动")
    assert ranked[0]["meaning"] == "旧心结"


@pytest.mark.asyncio
async def test_legacy_fields_accumulate_without_overwriting_other_kinds(db_session):
    await _seed_project(db_session, "p-legacy")
    db_session.add_all([
        CharacterState(project_id="p-legacy", chapter_number=12, character_name="甲",
                       extra={"significance": {"unspoken": "仍未和解", "cost": "抵押了祖屋"}}),
        CharacterState(project_id="p-legacy", chapter_number=13, character_name="甲",
                       extra={"significance": {"belief_shift": "愿意接受帮助"}}),
    ])
    await db_session.flush()
    brief = await CharacterSignificanceService().build_significance_brief(
        project_id="p-legacy", chapter_number=14, session=db_session)
    assert all(s in brief for s in ("仍未和解", "抵押了祖屋", "愿意接受帮助", "旧记录待核对"))

@pytest.mark.asyncio
@pytest.mark.parametrize("enabled,tier,expected", [(True, "flagship", 1), (False, "flagship", 0), (True, "free", 0)])
async def test_selected_and_edited_versions_keep_quality_gate(db_session, monkeypatch, enabled, tier, expected):
    from app.services.chapter_post_processor import ChapterPostProcessor
    from app.services.pipeline_config_service import PipelineConfigService
    import app.core.feature_gating as gates
    from sqlalchemy import select
    await _seed_project(db_session, "p-gate")
    chapter = (await db_session.execute(select(Chapter).where(
        Chapter.project_id == "p-gate", Chapter.chapter_number == 4))).scalars().first()
    parent = await db_session.get(ChapterVersion, chapter.selected_version_id)
    parent.metadata_ = {"character_significance_enabled": enabled}
    edited = ChapterVersion(chapter_id=chapter.id, parent_version_id=parent.id, content="沈青崖再次把令牌放下。")
    db_session.add(edited)
    await db_session.flush()
    chapter.selected_version_id = edited.id
    await db_session.commit()
    monkeypatch.setattr(PipelineConfigService, "_load_quality_loop_switches",
                        AsyncMock(return_value={"character_significance": False}))
    monkeypatch.setattr(gates, "get_user_tier", AsyncMock(return_value=tier))
    monkeypatch.setattr(gates, "load_flow_override_min_tiers",
                        AsyncMock(return_value={"enable_character_significance": "flagship"}))
    extract = AsyncMock(return_value={"stored": 1})
    monkeypatch.setattr(CharacterSignificanceService, "extract_and_store", extract)
    processor = ChapterPostProcessor(db_session, SimpleNamespace())
    await processor.process_character_significance(
        project_id="p-gate", chapter_number=4, content=edited.content, user_id=1)
    assert extract.await_count == expected
    if expected:
        assert extract.await_args.kwargs["chapter_content"] == edited.content


@pytest.mark.asyncio
async def test_switching_version_during_extraction_discards_delayed_result(db_session):
    from sqlalchemy import select
    await _seed_project(db_session, "p-race")
    async def switched(**kwargs):
        chapter = (await db_session.execute(select(Chapter).where(
            Chapter.project_id == "p-race", Chapter.chapter_number == 4))).scalars().first()
        new = ChapterVersion(chapter_id=chapter.id, content="沈青崖收回了令牌。")
        db_session.add(new)
        await db_session.flush()
        chapter.selected_version_id = new.id
        await db_session.commit()
        return _result()
    result = await CharacterSignificanceService().extract_and_store(
        project_id="p-race", chapter_number=4, chapter_content=_CHAPTER_TEXT,
        character_names=["沈青崖"], session=db_session,
        llm_service=SimpleNamespace(generate_structured=switched), prompt_service=_prompts())
    assert result == {"skipped": "source_changed"}


@pytest.mark.asyncio
async def test_significance_uses_canonical_row_when_old_data_has_duplicate_chapters(db_session):
    from app.services.chapter_post_processor import ChapterPostProcessor
    await _seed_project(db_session, "p-duplicate")
    newer, version = await _seed_chapter(db_session, "p-duplicate", 4, "沈青崖收回了令牌。")
    processor = ChapterPostProcessor(db_session, SimpleNamespace())
    for with_summary in (False, True):
        if with_summary:
            newer.real_summary = "较完整的章节行"
            await db_session.commit()
        canonical = await processor._get_canonical_chapter("p-duplicate", 4)
        source = (await CharacterSignificanceService._sources(db_session, "p-duplicate", 5, 4))[4]
        assert source["chapter_id"] == canonical.id
        assert source["version_id"] == canonical.selected_version_id
