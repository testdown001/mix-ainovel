# AIMETA P=写作质量更新回归测试|R=采样评审_护栏本地修补_推荐版本序列化|NR=不含生产代码|E=pytest|X=internal|A=测试函数|D=pytest|S=none|RD=./README.ai
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.api.routers import novels, writer
from app.db.init_db import is_schema_mismatch_error
from app.services.ai_review_service import AIReviewService
from app.services.chapter_guardrails import GuardrailResult, Violation, ChapterGuardrails
from app.services.novel_service import NovelService


def test_ai_review_uses_head_middle_tail_sampling_for_long_text():
    long_text = "A" * 1400 + "B" * 1400 + "C" * 1400
    sampled, is_sampled = AIReviewService._sample_content_for_review(long_text)

    assert is_sampled is True
    assert "[开头片段]" in sampled
    assert "[中段片段]" in sampled
    assert "[结尾片段]" in sampled
    assert "A" * 200 in sampled
    assert "B" * 200 in sampled
    assert "C" * 200 in sampled


def test_ai_review_keeps_short_text_without_sampling():
    short_text = "这是一个短文本"
    sampled, is_sampled = AIReviewService._sample_content_for_review(short_text)
    assert is_sampled is False
    assert sampled == short_text


def test_guardrail_local_patch_fixes_forbidden_name_and_omniscient_cue():
    guardrails = ChapterGuardrails()
    text = "与此同时，张三走进门内。"
    result = GuardrailResult(
        passed=False,
        violations=[
            Violation(
                type="omniscient_cue",
                severity="medium",
                description="出现全知视角 cue 词「与此同时」",
            ),
            Violation(
                type="forbidden_name",
                severity="high",
                description="出现了禁止角色「张三」的名字",
            ),
        ],
    )

    patched = guardrails.apply_local_patches(text, result)
    assert "与此同时" not in patched
    assert "张三" not in patched
    assert "那人" in patched


def test_guardrail_local_patch_strips_markdown_and_trims_trailing_camera():
    guardrails = ChapterGuardrails()
    text = "**小标题**\n他转身离开。身后传来脚步。"
    trailing_pos = text.find("身后")
    result = GuardrailResult(
        passed=False,
        violations=[
            Violation(
                type="markdown_marker",
                severity="medium",
                description="正文包含 Markdown 标签「**小标题**」",
            ),
            Violation(
                type="trailing_camera",
                severity="high",
                description="章末滞后镜头",
                position=trailing_pos,
            ),
        ],
    )

    patched = guardrails.apply_local_patches(text, result)
    assert "**" not in patched
    assert "身后传来脚步" not in patched


def test_chapter_schema_includes_recommended_version_from_ai_review():
    service = NovelService(session=None)  # _build_chapter_schema 不依赖 session

    now = datetime.utcnow()
    version1 = SimpleNamespace(
        id=11,
        content="版本一",
        created_at=now,
        metadata={"ai_review": {"is_best": False}, "foo": "bar"},
        version_label="v1",
    )
    version2 = SimpleNamespace(
        id=12,
        content="版本二",
        created_at=now + timedelta(seconds=1),
        metadata={"ai_review": {"is_best": True}},
        version_label="v2",
    )
    selected_version = version1

    chapter = SimpleNamespace(
        chapter_number=1,
        real_summary="真实摘要",
        selected_version=selected_version,
        selected_version_id=selected_version.id,
        versions=[version2, version1],  # 故意打乱顺序，验证按 created_at 排序
        evaluations=[],
        status="waiting_for_confirm",
        word_count=1234,
    )
    outline = SimpleNamespace(chapter_number=1, title="第一章", summary="摘要")
    project = SimpleNamespace(outlines=[outline], chapters=[chapter])

    schema = service._build_chapter_schema(project, 1, include_content=True)

    assert schema.versions == ["版本一", "版本二"]
    assert schema.version_metadata is not None
    assert schema.version_metadata[0]["version_id"] == 11
    assert schema.version_metadata[1]["version_id"] == 12
    assert schema.recommended_version_index == 1
    assert schema.word_count == 1234


def test_schema_mismatch_error_detects_missing_columns():
    err = RuntimeError("(1054, \"Unknown column 'chapter_blueprints.strand_type' in 'field list'\")")
    assert is_schema_mismatch_error(err) is True


def test_select_chapter_version_uses_outline_title_for_ingest(monkeypatch):
    class _ScalarResult:
        def __init__(self, value):
            self._value = value

        def scalars(self):
            return self

        def first(self):
            return self._value

    selected_version = SimpleNamespace(content="章节正文")
    chapter = SimpleNamespace(real_summary="已有摘要")
    novel_service = SimpleNamespace(
        ensure_project_owner=AsyncMock(return_value=SimpleNamespace()),
        get_or_create_chapter=AsyncMock(return_value=chapter),
        select_chapter_version=AsyncMock(return_value=selected_version),
    )
    ingest_chapter = AsyncMock()
    fake_session = SimpleNamespace(
        execute=AsyncMock(return_value=_ScalarResult(SimpleNamespace(title="第一章"))),
        rollback=AsyncMock(),
    )
    load_schema = AsyncMock(return_value="schema")

    monkeypatch.setattr(writer, "NovelService", lambda session: novel_service)
    monkeypatch.setattr(writer, "LLMService", lambda session: SimpleNamespace())
    monkeypatch.setattr(
        writer,
        "ChapterIngestionService",
        lambda llm_service: SimpleNamespace(ingest_chapter=ingest_chapter),
    )
    monkeypatch.setattr(writer, "_load_project_schema", load_schema)

    result = asyncio.run(
        writer.select_chapter_version(
            "project-1",
            SimpleNamespace(chapter_number=1, version_index=0),
            fake_session,
            SimpleNamespace(id=7),
        )
    )

    assert result == "schema"
    assert ingest_chapter.await_args.kwargs["title"] == "第一章"


def test_generate_concepts_serializes_project_object(monkeypatch):
    project = SimpleNamespace(id="project-1")
    project_schema = SimpleNamespace(
        blueprint=SimpleNamespace(
            title="蓝图标题",
            genre="玄幻",
            full_synopsis="故事梗概",
            world_setting={"era": "架空"},
            characters=[{"name": "林凡", "identity": "主角"}],
        )
    )
    novel_service = SimpleNamespace(
        ensure_project_owner=AsyncMock(return_value=project),
        _serialize_project=AsyncMock(return_value=project_schema),
    )
    llm_service = SimpleNamespace(get_llm_response=AsyncMock(return_value='{"concepts": []}'))
    fake_session = SimpleNamespace(commit=AsyncMock())

    monkeypatch.setattr(novels, "NovelService", lambda session: novel_service)
    monkeypatch.setattr(novels, "LLMService", lambda session: llm_service)

    result = asyncio.run(
        novels.generate_concepts(
            "project-1",
            fake_session,
            SimpleNamespace(id=7),
        )
    )

    assert result["status"] == "success"
    novel_service.ensure_project_owner.assert_awaited_once_with("project-1", 7)
    novel_service._serialize_project.assert_awaited_once_with(project)
    llm_kwargs = llm_service.get_llm_response.await_args.kwargs
    assert "蓝图标题" in llm_kwargs["system_prompt"]
    assert "林凡(主角)" in llm_kwargs["system_prompt"]
    assert llm_kwargs["conversation_history"] == [{"role": "user", "content": "请提取所有概念。"}]
    assert "user_message" not in llm_kwargs


def test_generate_chapter_scenes_uses_conversation_history(monkeypatch):
    outline = SimpleNamespace(title="第一章", summary="章节摘要", metadata_={})

    class _ExecResult:
        def scalar_one_or_none(self):
            return outline

    llm_service = SimpleNamespace(get_llm_response=AsyncMock(return_value='{"scenes": []}'))
    fake_session = SimpleNamespace(
        execute=AsyncMock(return_value=_ExecResult()),
        commit=AsyncMock(),
    )

    monkeypatch.setattr(novels, "LLMService", lambda session: llm_service)

    result = asyncio.run(
        novels.generate_chapter_scenes(
            "project-1",
            1,
            fake_session,
            SimpleNamespace(id=7),
        )
    )

    assert result["status"] == "success"
    assert result["scenes"] == []
    llm_kwargs = llm_service.get_llm_response.await_args.kwargs
    assert llm_kwargs["conversation_history"] == [{"role": "user", "content": "请拆分场景。"}]
    assert "user_message" not in llm_kwargs


def test_advanced_generate_stream_uses_internal_session_scope(monkeypatch):
    import app.agents.hybrid_executor as hybrid_executor_module

    session_lifecycle = []
    fake_session = SimpleNamespace(rollback=AsyncMock())
    captured = {}

    class _SessionContext:
        async def __aenter__(self):
            session_lifecycle.append("enter")
            return fake_session

        async def __aexit__(self, exc_type, exc, tb):
            session_lifecycle.append("exit")

    class _FlowConfig:
        use_agent = False
        preset = "balanced"
        async_finalize = False

        def model_dump(self):
            return {
                "use_agent": self.use_agent,
                "preset": self.preset,
                "async_finalize": self.async_finalize,
            }

    class _FakeHybridExecutor:
        def __init__(self, session, user_id):
            captured["session"] = session
            captured["user_id"] = user_id

        def enable_agent_system(self):
            captured["agent_enabled"] = True

        async def generate_chapter(self, **kwargs):
            captured["kwargs"] = kwargs
            await kwargs["stream_handler"]({"event": "stage", "message": "生成中"})
            return {"variants": [], "best_version_index": 0}

    async def _collect_stream(response):
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    monkeypatch.setattr(writer, "AsyncSessionLocal", lambda: _SessionContext())
    monkeypatch.setattr(hybrid_executor_module, "HybridExecutor", _FakeHybridExecutor)

    response = asyncio.run(
        writer.advanced_generate_chapter_stream(
            SimpleNamespace(
                project_id="project-1",
                chapter_number=3,
                writing_notes="补充说明",
                flow_config=_FlowConfig(),
            ),
            SimpleNamespace(id=7),
        )
    )
    payload = asyncio.run(_collect_stream(response))

    assert captured["session"] is fake_session
    assert captured["user_id"] == 7
    assert captured["kwargs"]["project_id"] == "project-1"
    assert captured["kwargs"]["chapter_number"] == 3
    assert session_lifecycle == ["enter", "exit"]
    assert "event: started" in payload
    assert "event: stage" in payload
    assert "event: completed" in payload
