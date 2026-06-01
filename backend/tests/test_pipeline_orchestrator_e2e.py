"""PipelineOrchestrator.generate_chapter 端到端集成测试（真内存 SQLite，仅 mock LLM 出口）。

这是对"唯一真实生成引擎"的首个端到端覆盖：真实走 config 解析 → 项目/纲要加载 →
章节创建 → 历史/上下文组装 → fast 路径单版本生成 → 持久化，仅把外部 LLM 边界
(LLMService.get_llm_response / chat_with_tools) 替换为确定性桩，向量库默认关闭。

覆盖报告 P2-D 指出的盲区：现存测试都用 Mock session，主路径"查到数据后的分支"从未真正执行。
"""
import asyncio
import json

import pytest

import app.models  # noqa: F401  触发 mapper 注册
from app.db.base import Base

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

FAKE_CHAPTER = (
    "夜色压在城墙上，林玄握紧手中的断剑，一步步走向那扇紧闭的铁门。"
    "他知道门后是什么，也知道一旦推开就再无退路。风从巷口灌入，"
    "卷起地上的尘土，像是为他送行。他深吸一口气，掌心的灵力缓缓凝聚，"
    "在指尖跳动成一簇微光。这一夜，注定要有人血溅长街。"
) * 6  # 约 600+ 字，满足最小字数校验


def _smart_llm_response(*args, **kwargs):
    """根据 response_format 返回 JSON 或散文，覆盖 mission/摘要/正文等多种调用。"""
    response_format = kwargs.get("response_format")
    if response_format in ("json", "json_object"):
        # 给一个宽松的 JSON，让解析方走默认分支而不崩
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


def _make_sessionmaker():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _seed(session):
    from app.models.user import User
    from app.models.novel import NovelProject, NovelBlueprint, BlueprintCharacter, ChapterOutline

    user = User(id=1, username="e2e_user", hashed_password="x", is_active=True)
    project = NovelProject(id="e2e-proj-1", user_id=1, title="测试小说", status="writing")
    blueprint = NovelBlueprint(
        project_id="e2e-proj-1",
        title="测试小说",
        genre="玄幻",
        style="热血",
        tone="紧张",
        one_sentence_summary="少年持断剑闯城。",
        full_synopsis="一个少年为复仇踏入危机四伏的城池。",
        world_setting={"era": "架空"},
    )
    character = BlueprintCharacter(
        project_id="e2e-proj-1", name="林玄", identity="主角",
        personality="坚毅", goals="复仇", position=0,
    )
    outline = ChapterOutline(
        project_id="e2e-proj-1", chapter_number=1,
        title="血溅长街", summary="林玄推开铁门，与守卫激战。",
    )
    session.add_all([user, project, blueprint, character, outline])
    await session.commit()


async def _run():
    from app.services.prompt_service import PromptService
    from app.services.pipeline_orchestrator import PipelineOrchestrator

    engine, Session = _make_sessionmaker()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as session:
        await _seed(session)
        # 预载提示词模板（mission/writing 等），否则 PromptService 取不到模板
        await PromptService(session).preload()
        await session.commit()

    async with Session() as session:
        orch = PipelineOrchestrator(session)
        result = await orch.generate_chapter(
            project_id="e2e-proj-1",
            chapter_number=1,
            user_id=1,
            writing_notes="保持紧张节奏",
            flow_config={"preset": "fast", "versions": 1},
        )

    await engine.dispose()
    return result


_FAKE_WRITER_PROMPT = (
    "你是一位资深网文作者。请根据给定的章节大纲、人物设定与前文摘要，"
    "写出本章正文，保持紧凑节奏与人物一致性。直接输出正文。"
)


async def _fake_prefetch_writer_prompt(self, *args, **kwargs):
    # 写作提示词模板属于外部配置；用固定模板替代（其取数走独立 AsyncSessionLocal，
    # 与注入的内存测试 session 不是同一连接，故在此桩掉）。
    return _FAKE_WRITER_PROMPT


@pytest.fixture(autouse=True)
def _patch_external(monkeypatch):
    # 仅 mock 外部 LLM 出口
    from app.services.llm_service import LLMService
    monkeypatch.setattr(LLMService, "get_llm_response", _fake_get_llm_response)
    monkeypatch.setattr(LLMService, "chat_with_tools", _fake_chat_with_tools)
    # 写作提示词（外部配置，走独立 session）固定化
    from app.services.writer_prompt_service import WriterPromptService
    monkeypatch.setattr(WriterPromptService, "prefetch_writer_prompt", _fake_prefetch_writer_prompt)
    # 屏蔽 Redis 缓存（避免连接尝试）
    from app.services.cache_service import CacheService

    async def _none(self, *a, **k):
        return None

    monkeypatch.setattr(CacheService, "get_project_schema", _none)
    monkeypatch.setattr(CacheService, "set_project_schema", _none)
    monkeypatch.setattr(CacheService, "invalidate_project_schema", _none)


def test_generate_chapter_fast_path_end_to_end():
    result = asyncio.run(_run())
    assert isinstance(result, dict)
    # 归一化结果应含变体/最佳版本
    variants = result.get("variants") or result.get("versions") or []
    assert variants, f"未产出任何版本: keys={list(result.keys())}"
    content = variants[0].get("content") if isinstance(variants[0], dict) else None
    assert content and len(content) > 50
