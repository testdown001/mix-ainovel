"""滚动细纲修订回路 (A1)：OutlineRevisionService + config 门控。

覆盖：
- _write_hint merge 不覆盖导演脚本（核心安全约束）；
- _format_brief 格式化 / 无内容返回 None；
- review_downstream：写入 revision_hint(merge) / 越界章号跳过 / 无后续大纲降级 / 未配置提示词降级；
- build_revision_brief：pending 出文本 / 非 pending / 无 hint / 无大纲 → None；
- config：仅 premium + 开关开 → enable_outline_revision True；fast/standard/开关关 → False。
不触网、不触真 LLM（generate_structured 注入桩）。
"""
import asyncio
from types import SimpleNamespace

import app.models  # noqa: F401  mapper 注册
from app.db.base import Base
from app.services import pipeline_config_service as config_module
from app.services.outline_revision_service import (
    OutlineRevisionItem,
    OutlineRevisionResult,
    OutlineRevisionService,
)
from app.services.pipeline_config_service import PipelineConfigService

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


def _make_sessionmaker():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


class _FakeLLM:
    def __init__(self, result):
        self._result = result
        self.calls = 0

    async def generate_structured(self, **kwargs):
        self.calls += 1
        return self._result


class _FakePrompt:
    def __init__(self, prompt="SYSTEM PROMPT"):
        self._prompt = prompt

    async def get_prompt(self, name):
        return self._prompt


async def _seed_outline(session, project_id, ch, title, summary, metadata=None):
    from app.models.novel import ChapterOutline

    outline = ChapterOutline(
        project_id=project_id,
        chapter_number=ch,
        title=title,
        summary=summary,
        metadata=metadata,
    )
    session.add(outline)
    await session.flush()
    return outline


# ----------------------------------------------------------------- 纯单元
def test_write_hint_merges_without_clobbering_director_script():
    """核心安全约束：写 revision_hint 不能覆盖既有导演脚本等 metadata。"""
    outline = SimpleNamespace(metadata={"director_script": {"beats": [1, 2]}, "foo": "bar"})
    item = OutlineRevisionItem(
        chapter_number=6, severity="high", reason="和解了", suggestion="改为分歧"
    )
    OutlineRevisionService._write_hint(outline, source_chapter=5, item=item)

    assert outline.metadata["director_script"] == {"beats": [1, 2]}  # 未被覆盖
    assert outline.metadata["foo"] == "bar"
    hint = outline.metadata["revision_hint"]
    assert hint == {
        "source_chapter": 5,
        "severity": "high",
        "reason": "和解了",
        "suggestion": "改为分歧",
        "status": "pending",
    }


def test_write_hint_on_empty_metadata():
    outline = SimpleNamespace(metadata=None)
    item = OutlineRevisionItem(chapter_number=6, suggestion="x")
    OutlineRevisionService._write_hint(outline, source_chapter=5, item=item)
    assert outline.metadata["revision_hint"]["status"] == "pending"
    assert outline.metadata["revision_hint"]["severity"] == "medium"  # 默认


def test_format_brief_renders_and_degrades():
    text = OutlineRevisionService._format_brief(
        {"source_chapter": 5, "severity": "high", "reason": "和解了", "suggestion": "改为分歧"}
    )
    assert text is not None
    assert "大纲修订提示" in text
    assert "第5章" in text
    assert "改为分歧" in text
    # 既无 reason 又无 suggestion → None
    assert OutlineRevisionService._format_brief({"severity": "high"}) is None


# ----------------------------------------------------------------- 写侧（DB + 桩 LLM）
def test_review_downstream_writes_hint_and_merges():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed_outline(session, "p1", 5, "第五章", "原大纲5")
            await _seed_outline(
                session, "p1", 6, "第六章", "冲突升级",
                metadata={"director_script": {"beats": [1, 2]}},
            )
            await _seed_outline(session, "p1", 7, "第七章", "原大纲7")
            await session.commit()

            result = OutlineRevisionResult(
                revisions=[
                    OutlineRevisionItem(
                        chapter_number=6, severity="high", reason="和解了", suggestion="改为分歧"
                    ),
                    OutlineRevisionItem(chapter_number=99, reason="越界", suggestion="x"),
                ]
            )
            llm = _FakeLLM(result)
            svc = OutlineRevisionService()
            stats = await svc.review_downstream(
                project_id="p1",
                finalized_chapter_number=5,
                chapter_content="本章实际正文……",
                session=session,
                llm_service=llm,
                prompt_service=_FakePrompt(),
            )

            assert llm.calls == 1
            assert stats["reviewed"] == 2  # lookahead=3 → 6,7,8；仅 6,7 存在
            assert stats["hints_written"] == 1  # 仅 ch6（99 越界跳过）

            ch6 = await svc._get_outline(session, "p1", 6)
            hint = ch6.metadata["revision_hint"]
            assert hint["status"] == "pending"
            assert hint["source_chapter"] == 5
            assert hint["suggestion"] == "改为分歧"
            assert ch6.metadata["director_script"] == {"beats": [1, 2]}  # 导演脚本保留

            ch7 = await svc._get_outline(session, "p1", 7)
            assert "revision_hint" not in (ch7.metadata or {})
        await engine.dispose()

    asyncio.run(_run())


def test_review_downstream_no_downstream_degrades():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed_outline(session, "p1", 5, "第五章", "原大纲5")  # 仅当前章，无后续
            await session.commit()
            llm = _FakeLLM(OutlineRevisionResult())
            stats = await OutlineRevisionService().review_downstream(
                project_id="p1",
                finalized_chapter_number=5,
                chapter_content="正文",
                session=session,
                llm_service=llm,
                prompt_service=_FakePrompt(),
            )
            assert stats == {"reviewed": 0, "hints_written": 0}
            assert llm.calls == 0  # 无后续大纲 → 根本不调 LLM
        await engine.dispose()

    asyncio.run(_run())


def test_review_downstream_no_prompt_degrades():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed_outline(session, "p1", 6, "第六章", "原大纲6")
            await session.commit()
            llm = _FakeLLM(OutlineRevisionResult())

            class _NoPrompt:
                async def get_prompt(self, name):
                    return None

            stats = await OutlineRevisionService().review_downstream(
                project_id="p1",
                finalized_chapter_number=5,
                chapter_content="正文",
                session=session,
                llm_service=llm,
                prompt_service=_NoPrompt(),
            )
            assert stats == {"reviewed": 0, "hints_written": 0}
            assert llm.calls == 0
        await engine.dispose()

    asyncio.run(_run())


# ----------------------------------------------------------------- 读侧（DB）
def test_build_revision_brief_cases():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed_outline(
                session, "p1", 6, "第六章", "原大纲6",
                metadata={"revision_hint": {
                    "source_chapter": 5, "severity": "high",
                    "reason": "和解了", "suggestion": "改为分歧", "status": "pending",
                }},
            )
            await _seed_outline(
                session, "p1", 7, "第七章", "原大纲7",
                metadata={"revision_hint": {
                    "source_chapter": 5, "reason": "x", "suggestion": "y", "status": "accepted",
                }},
            )
            await _seed_outline(session, "p1", 8, "第八章", "原大纲8")  # 无 hint
            await session.commit()

            svc = OutlineRevisionService()
            # pending → 出文本
            text = await svc.build_revision_brief(project_id="p1", chapter_number=6, session=session)
            assert text is not None and "改为分歧" in text
            # 非 pending(accepted) → None
            assert await svc.build_revision_brief(project_id="p1", chapter_number=7, session=session) is None
            # 无 hint → None
            assert await svc.build_revision_brief(project_id="p1", chapter_number=8, session=session) is None
            # 无大纲 → None
            assert await svc.build_revision_brief(project_id="p1", chapter_number=999, session=session) is None
        await engine.dispose()

    asyncio.run(_run())


# ----------------------------------------------------------------- config 门控
async def _resolve(flow_config):
    engine, Session = _make_sessionmaker()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with Session() as session:
        config = await PipelineConfigService(session).resolve_config(flow_config)
    await engine.dispose()
    return config


def test_enable_outline_revision_only_premium_with_switch(monkeypatch):
    # premium 但开关关 → False
    monkeypatch.setattr(config_module.settings, "outline_revision_enabled", False, raising=False)
    assert asyncio.run(_resolve({"preset": "premium"})).enable_outline_revision is False

    # premium + 开关开 → True
    monkeypatch.setattr(config_module.settings, "outline_revision_enabled", True, raising=False)
    assert asyncio.run(_resolve({"preset": "premium"})).enable_outline_revision is True

    # standard + 开关开 → 仍 False（非 flagship）
    assert asyncio.run(_resolve({"preset": "standard"})).enable_outline_revision is False
    # fast + 开关开 → False
    assert asyncio.run(_resolve({"preset": "fast"})).enable_outline_revision is False
