"""重生成不毁章回归测试（真内存 SQLite，仅 mock LLM 出口）。

覆盖场景：一个已完稿章节（有 real_summary、有选中版本）被重新生成时——
- 失败路径：生成流中途抛异常（LLM 报错/超时/护栏拒绝），章节的 real_summary /
  selected_version_id / 旧版本内容必须原样保留，不得在生成开始前就被清空；
- 成功路径：新版本落库时（replace_chapter_versions 同一事务）才清理旧状态：
  先解除选中引用、删除旧版本、清空 real_summary 供后处理重算。

历史缺陷：pipeline_orchestrator 在生成开始前就把 real_summary=None、
selected_version_id=None commit，任何中途失败都会让完稿章节退化为
无摘要、无选中版本。
"""
import asyncio
import json

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  触发全部 mapper 注册
import app.models.user_quota  # noqa: F401  防 mapper KeyError
from app.db.base import Base

FAKE_CHAPTER = (
    "夜色压在城墙上，林玄握紧手中的断剑，一步步走向那扇紧闭的铁门。"
    "他知道门后是什么，也知道一旦推开就再无退路。风从巷口灌入，"
    "卷起地上的尘土，像是为他送行。他深吸一口气，掌心的灵力缓缓凝聚，"
    "在指尖跳动成一簇微光。这一夜，注定要有人血溅长街。"
) * 6

OLD_SUMMARY = "旧摘要：林玄初入城池，结识盟友。"
OLD_CONTENT = "这是已完稿的旧版本正文。" * 30


def _smart_llm_response(*args, **kwargs):
    response_format = kwargs.get("response_format")
    if response_format in ("json", "json_object"):
        return json.dumps({
            "summary": "本章梗概占位",
            "goals": [],
            "scenes": [],
            "key_points": [],
        }, ensure_ascii=False)
    return FAKE_CHAPTER


async def _fake_get_llm_response(self, *args, **kwargs):
    return _smart_llm_response(*args, **kwargs)


async def _fake_chat_with_tools(self, *args, **kwargs):
    return {"content": FAKE_CHAPTER, "tool_calls": [], "finish_reason": "stop"}


_FAKE_WRITER_PROMPT = (
    "你是一位资深网文作者。请根据给定的章节大纲、人物设定与前文摘要，"
    "写出本章正文。直接输出正文。"
)


async def _fake_prefetch_writer_prompt(self, *args, **kwargs):
    return _FAKE_WRITER_PROMPT


def _make_engine(enable_fk: bool = False):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    if enable_fk:
        @event.listens_for(engine.sync_engine, "connect")
        def _set_fk(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _seed_completed_chapter(session):
    """播种一个已完稿章节：有 real_summary、有版本且被选中。返回旧版本 id。"""
    from app.models.user import User
    from app.models.novel import (
        NovelProject, NovelBlueprint, BlueprintCharacter,
        ChapterOutline, Chapter, ChapterVersion,
    )

    user = User(id=1, username="regen_user", hashed_password="x", is_active=True)
    project = NovelProject(id="regen-proj-1", user_id=1, title="测试小说", status="writing")
    blueprint = NovelBlueprint(
        project_id="regen-proj-1",
        title="测试小说",
        genre="玄幻",
        style="热血",
        tone="紧张",
        one_sentence_summary="少年持断剑闯城。",
        full_synopsis="一个少年为复仇踏入危机四伏的城池。",
        world_setting={"era": "架空"},
    )
    character = BlueprintCharacter(
        project_id="regen-proj-1", name="林玄", identity="主角",
        personality="坚毅", goals="复仇", position=0,
    )
    outline = ChapterOutline(
        project_id="regen-proj-1", chapter_number=1,
        title="血溅长街", summary="林玄推开铁门，与守卫激战。",
    )
    session.add_all([user, project, blueprint, character, outline])
    await session.commit()

    chapter = Chapter(
        project_id="regen-proj-1", chapter_number=1,
        real_summary=OLD_SUMMARY, status="successful",
        word_count=len(OLD_CONTENT),
    )
    session.add(chapter)
    await session.commit()
    await session.refresh(chapter)

    version = ChapterVersion(chapter_id=chapter.id, content=OLD_CONTENT, version_label="v1")
    session.add(version)
    await session.commit()
    await session.refresh(version)

    chapter.selected_version_id = version.id
    await session.commit()
    return chapter.id, version.id


@pytest.fixture(autouse=True)
def _patch_external(monkeypatch):
    from app.services.llm_service import LLMService
    monkeypatch.setattr(LLMService, "get_llm_response", _fake_get_llm_response)
    monkeypatch.setattr(LLMService, "chat_with_tools", _fake_chat_with_tools)
    from app.services.writer_prompt_service import WriterPromptService
    monkeypatch.setattr(WriterPromptService, "prefetch_writer_prompt", _fake_prefetch_writer_prompt)
    from app.services.cache_service import CacheService

    async def _none(self, *a, **k):
        return None

    monkeypatch.setattr(CacheService, "get_project_schema", _none)
    monkeypatch.setattr(CacheService, "set_project_schema", _none)
    monkeypatch.setattr(CacheService, "invalidate_project_schema", _none)


async def _run_regen(monkeypatch, *, fail_generation: bool):
    from app.services.prompt_service import PromptService
    from app.services.pipeline_orchestrator import PipelineOrchestrator
    from app.models.novel import Chapter, ChapterVersion

    engine, Session = _make_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as session:
        chapter_id, old_version_id = await _seed_completed_chapter(session)
        await PromptService(session).preload()
        await session.commit()

    if fail_generation:
        from app.services.fast_generation_flow_service import FastGenerationFlowService

        async def _boom(self, *args, **kwargs):
            raise RuntimeError("模拟 LLM 中途失败")

        monkeypatch.setattr(FastGenerationFlowService, "run", _boom)

    error = None
    async with Session() as session:
        orch = PipelineOrchestrator(session)
        try:
            await orch.generate_chapter(
                project_id="regen-proj-1",
                chapter_number=1,
                user_id=1,
                writing_notes="保持紧张节奏",
                flow_config={"preset": "fast", "versions": 1},
            )
        except RuntimeError as exc:
            error = exc

    async with Session() as session:
        chapter = (await session.execute(
            select(Chapter).where(Chapter.id == chapter_id)
        )).scalars().one()
        versions = (await session.execute(
            select(ChapterVersion).where(ChapterVersion.chapter_id == chapter_id)
        )).scalars().all()

    await engine.dispose()
    return error, chapter, versions, old_version_id


def test_generation_failure_preserves_summary_and_selected_version(monkeypatch):
    """生成中途失败：已完稿章节的摘要/选中版本/旧正文必须原样保留。"""
    error, chapter, versions, old_version_id = asyncio.run(
        _run_regen(monkeypatch, fail_generation=True)
    )
    assert error is not None, "生成流异常应向上传播"
    assert chapter.real_summary == OLD_SUMMARY, "失败后 real_summary 不得被清空"
    assert chapter.selected_version_id == old_version_id, "失败后选中版本不得被清空"
    assert len(versions) == 1 and versions[0].content == OLD_CONTENT, "失败后旧版本正文必须还在"


def test_generation_success_appends_candidates_without_unselecting_confirmed_text(monkeypatch):
    """H2 重起草：候选追加，但作者确认前当前正文、摘要与修订基线保持不变。"""
    error, chapter, versions, old_version_id = asyncio.run(
        _run_regen(monkeypatch, fail_generation=False)
    )
    assert error is None
    assert versions, "成功路径应写入新版本"
    assert any(v.content == OLD_CONTENT for v in versions), "M3 必须保留旧版本供历史恢复"
    assert any(v.content != OLD_CONTENT for v in versions), "成功路径应写入新候选版本"
    assert chapter.real_summary == OLD_SUMMARY, "作者选版前不得清空当前正文摘要"
    assert chapter.selected_version_id == old_version_id, "作者选版前不得取消当前正文"
    assert chapter.status == "waiting_for_confirm"


@pytest.mark.asyncio
async def test_replace_chapter_versions_preserves_current_selection_with_fk_on():
    """H2 在 FK 约束开启时保留当前选中引用，并追加新候选而不删除旧快照。"""
    from app.services.novel_service import NovelService
    from app.models.novel import Chapter, ChapterVersion
    from app.models.user import User
    from app.models.novel import NovelProject

    engine, Session = _make_engine(enable_fk=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as session:
        assert (await session.execute(text("PRAGMA foreign_keys"))).scalar() == 1

        session.add_all([
            User(id=1, username="fk_user", hashed_password="x", is_active=True),
            NovelProject(id="fk-proj", user_id=1, title="t", status="writing"),
        ])
        await session.commit()
        chapter = Chapter(
            project_id="fk-proj", chapter_number=1,
            real_summary=OLD_SUMMARY, status="successful",
        )
        session.add(chapter)
        await session.commit()
        await session.refresh(chapter)
        old = ChapterVersion(chapter_id=chapter.id, content=OLD_CONTENT, version_label="v1")
        session.add(old)
        await session.commit()
        await session.refresh(old)
        chapter.selected_version_id = old.id
        await session.commit()

        service = NovelService(session)
        new_versions = await service.replace_chapter_versions(chapter, ["全新正文" * 50])

        assert len(new_versions) == 1
        assert chapter.selected_version_id == old.id
        assert chapter.real_summary == OLD_SUMMARY
        remaining = (await session.execute(
            select(ChapterVersion).where(ChapterVersion.chapter_id == chapter.id)
        )).scalars().all()
        assert {v.id for v in remaining} == {old.id, new_versions[0].id}
        assert any(v.content == OLD_CONTENT for v in remaining)

    await engine.dispose()
