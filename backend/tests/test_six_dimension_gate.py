"""同步六维评审 + auto-refine 通电回归测试。

历史上该路径被四个叠加 bug 完全打死（review_chapter 不接受 user_id 必抛
TypeError 被吞、反馈键名与提示词输出结构不符、阈值读不存在的 config 字段、
解析失败兜底 80 分伪装通过）。本文件锁定修复后的行为：
- 低分 + critical issue → 触发 _run_combined_revision 并替换正文；
- 降级/异常 → 不触发重写，enhanced_review 标 status=degraded；
- review_chapter(user_id=...) 签名回归，且 user_id 透传到 generate_structured；
- 阈值来自 config.six_dimension_min_score（settings → resolve_config 填充），非硬编码。
"""
import asyncio
from types import SimpleNamespace

import pytest

import app.models  # noqa: F401  触发 mapper 注册（含 user_quota）
from app.services.six_dimension_review_service import (
    SixDimensionResult,
    SixDimensionReviewService,
)
from app.services.standard_post_processing_service import StandardPostProcessingService


class _FakeOrchestrator:
    """仅实现六维路径覆盖到的重写步骤，记录调用入参。"""

    def __init__(self):
        self.session = SimpleNamespace()
        self.llm_service = SimpleNamespace()
        self.prompt_service = SimpleNamespace()
        self.revision_calls: list[dict] = []

    async def _run_combined_revision(self, chapter_content=None, **kwargs):
        self.revision_calls.append({"chapter_content": chapter_content, **kwargs})
        return chapter_content + "·已重写", {"applied": True}


def _config(min_score: int = 70):
    return SimpleNamespace(
        enable_self_critique=False,
        enable_consistency=False,
        enable_humanization=False,
        enable_reader_sim=False,
        enable_anti_hallucination=False,
        use_local_anti_hallucination=False,
        enable_optimizer=False,
        enable_polish=False,
        enable_enrichment=False,
        enable_density_compression=False,
        enable_six_dimension=True,
        humanization_threshold=70,
        six_dimension_min_score=min_score,
    )


async def _run_postprocess(orch, config):
    svc = StandardPostProcessingService(orch)
    return await svc.run(
        best_content="正文",
        best_version={"content": "正文", "metadata": {}},
        ai_review_result=None,
        review_summaries={},
        config=config,
        project_id="proj-1",
        chapter_number=3,
        chapter_mission={"pov": "林玄"},
        writer_blueprint={"characters": []},
        history_context={"previous_summary": "上章摘要", "completed_chapters": []},
        user_id=1,
        chapter_word_count_min=2000,
        chapter_word_count_max=4000,
        chapter_target_word_count=3000,
        enhanced_flow=True,
        outline_title="第三章",
        forbidden_characters=[],
        allowed_new_characters=[],
    )


def _low_score_review(overall_score: int = 60):
    """按 prompts/six_dimension_review.md 的真实输出结构构造低分结果。"""
    return {
        "overall_score": overall_score,
        "dimensions": {
            "internal_consistency": {
                "score": 55,
                "issues": [
                    {
                        "severity": "critical",
                        "description": "主角动机前后矛盾",
                        "location": "第二幕",
                        "suggestion": "补一段动机铺垫",
                    },
                    {
                        "severity": "info",
                        "description": "轻微用词重复",
                        "location": "",
                        "suggestion": "",
                    },
                ],
            },
            "style_compliance": {"score": 90, "issues": []},
        },
        "critical_issues_count": 1,
        "warning_issues_count": 0,
        "info_issues_count": 1,
        "summary": "整体节奏拖沓，需收紧第二幕",
        "priority_fixes": [],
        "recommendations": [],
    }


def _patch_review(monkeypatch, payload=None, exc: Exception | None = None):
    async def _fake_review(self, **kwargs):
        if exc is not None:
            raise exc
        return payload

    monkeypatch.setattr(SixDimensionReviewService, "review_chapter", _fake_review)


@pytest.mark.asyncio
async def test_low_score_triggers_auto_refine(monkeypatch):
    _patch_review(monkeypatch, payload=_low_score_review(overall_score=60))
    orch = _FakeOrchestrator()
    result = await _run_postprocess(orch, _config(min_score=70))

    # 触发重写且正文被替换
    assert len(orch.revision_calls) == 1
    assert result["best_content"] == "正文·已重写"
    assert result["review_summaries"]["auto_refiner"]["triggered"] is True
    assert result["review_summaries"]["auto_refiner"]["original_score"] == 60
    assert result["review_summaries"]["enhanced_review"] == {"status": "completed", "score": 60}

    # 反馈提取对齐提示词真实结构：summary 作总评，critical issue 拼 description+suggestion
    call = orch.revision_calls[0]
    assert call["refinement_suggestions"] == "整体节奏拖沓，需收紧第二幕"
    assert len(call["critical_flaws"]) == 1  # info 级问题不进缺陷清单
    assert "主角动机前后矛盾" in call["critical_flaws"][0]
    assert "补一段动机铺垫" in call["critical_flaws"][0]


@pytest.mark.asyncio
async def test_degraded_result_skips_refine(monkeypatch):
    # 用真实的降级兜底结构（0 分 + degraded 标记），确保 0 分也不触发重写
    degraded = SixDimensionReviewService._create_default_result(
        SixDimensionReviewService.__new__(SixDimensionReviewService),
        "审查完成，但结果解析失败",
    )
    assert degraded["degraded"] is True
    assert degraded["overall_score"] == 0  # 不再是伪装通过的 80 分

    _patch_review(monkeypatch, payload=degraded)
    orch = _FakeOrchestrator()
    result = await _run_postprocess(orch, _config(min_score=70))

    assert orch.revision_calls == []
    assert result["best_content"] == "正文"
    assert result["review_summaries"]["enhanced_review"]["status"] == "degraded"
    assert "auto_refiner" not in result["review_summaries"]


@pytest.mark.asyncio
async def test_review_exception_marks_degraded(monkeypatch):
    _patch_review(monkeypatch, exc=RuntimeError("审查服务不可用"))
    orch = _FakeOrchestrator()
    result = await _run_postprocess(orch, _config(min_score=70))

    assert orch.revision_calls == []
    assert result["best_content"] == "正文"
    assert result["review_summaries"]["enhanced_review"]["status"] == "degraded"


@pytest.mark.asyncio
async def test_threshold_read_from_config_not_hardcoded(monkeypatch):
    # 阈值 90：75 分应触发重写（若硬编码 70 则不会触发）
    _patch_review(monkeypatch, payload=_low_score_review(overall_score=75))
    orch = _FakeOrchestrator()
    result = await _run_postprocess(orch, _config(min_score=90))
    assert len(orch.revision_calls) == 1
    assert result["review_summaries"]["auto_refiner"]["triggered"] is True

    # 对照组：阈值 70 时 75 分不触发
    orch2 = _FakeOrchestrator()
    result2 = await _run_postprocess(orch2, _config(min_score=70))
    assert orch2.revision_calls == []
    assert "auto_refiner" not in result2["review_summaries"]


class _RecordingLLM:
    def __init__(self, result_model):
        self.calls: list[dict] = []
        self._result_model = result_model

    async def generate_structured(self, *, prompt, schema, system_prompt=None, user_id=None, default=None, **kwargs):
        self.calls.append({"user_id": user_id})
        return self._result_model


def _make_review_service(llm, prompt_text):
    async def _get_prompt(name):
        return prompt_text

    async def _none(_project_id):
        return None

    prompt_service = SimpleNamespace(get_prompt=_get_prompt)
    constitution_service = SimpleNamespace(
        get_constitution=_none,
        get_constitution_context=lambda c: "（无宪法）",
    )
    persona_service = SimpleNamespace(
        get_active_persona=_none,
        get_persona_context=lambda p: "（无人格）",
    )
    return SixDimensionReviewService(
        SimpleNamespace(),  # db 不会被 review_chapter 直接使用
        llm,
        prompt_service,
        constitution_service,
        persona_service,
    )


@pytest.mark.asyncio
async def test_review_chapter_accepts_user_id_and_forwards_it():
    # 签名回归：user_id=1 不得抛 TypeError（历史 bug：调用方传了、签名没有）
    model = SixDimensionResult.model_validate(_low_score_review(overall_score=60))
    llm = _RecordingLLM(model)
    service = _make_review_service(llm, "审查 {{chapter_content}}")

    result = await service.review_chapter(
        project_id="proj-1",
        chapter_number=1,
        chapter_title="第一章",
        chapter_content="正文",
        user_id=1,
    )
    assert result["overall_score"] == 60
    # user_id 透传到 generate_structured（用于用量统计/限额归属）
    assert llm.calls == [{"user_id": 1}]


@pytest.mark.asyncio
async def test_review_chapter_missing_prompt_returns_degraded():
    llm = _RecordingLLM(None)
    service = _make_review_service(llm, prompt_text=None)

    result = await service.review_chapter(
        project_id="proj-1",
        chapter_number=1,
        chapter_title="第一章",
        chapter_content="正文",
        user_id=1,
    )
    assert result["degraded"] is True
    assert result["overall_score"] == 0
    assert llm.calls == []


def test_resolve_config_fills_six_dimension_min_score(monkeypatch):
    # resolve_config 应从 settings.six_dimension_min_score 填充（此前该字段从未生效）
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.core.config import settings
    from app.db.base import Base
    from app.services.pipeline_config_service import PipelineConfigService

    monkeypatch.setattr(settings, "six_dimension_min_score", 85)

    async def _resolve():
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with Session() as session:
            config = await PipelineConfigService(session).resolve_config({"preset": "standard"})
        await engine.dispose()
        return config

    config = asyncio.run(_resolve())
    assert config.enable_six_dimension is True
    assert config.six_dimension_min_score == 85
