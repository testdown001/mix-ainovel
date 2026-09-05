"""全文重写步骤（combined_revision / consistency auto_fix / enrichment / humanize）的正文校验守卫回归测试。

守卫统一形态：sanitize_chapter_plain_text → is_probable_chapter_plain_text → 0.5x 长度下限，
校验失败保留改写前文本。另含 optimizer prompt f-string 转义回归与显式 timeout 断言。
"""
import asyncio
import json

import pytest

import app.models.user_quota  # noqa: F401  防 SQLAlchemy mapper KeyError

from app.services.consistency_service import (
    ConsistencyCheckResult,
    ConsistencyService,
    ConsistencyViolation,
    ViolationSeverity,
)
from app.services.enrichment_service import EnrichmentService
from app.services.humanization_service import HumanizationService
from app.services.pipeline_review import PipelineReviewMixin
from app.services.llm_service import LLMService

CHAPTER_BODY = (
    "雨声砸在青瓦上，沈砚推开窗，冷风卷着潮气扑进屋内。"
    "街口的灯笼被风吹得一晃一晃，红光落在他的指节上，像一层迟迟不肯退去的血色。"
    "他听见楼下有人压低声音争吵，茶盏碰在桌沿，发出短促的一声响。"
    "那声音让他想起昨夜未写完的信，也想起信尾被墨水洇开的名字。"
)

# 模型把编辑任务拆解当正文输出的典型形态（应被守卫拦下）
ANALYSIS_OUTPUT = """修改思路：本次修订聚焦评审指出的三处缺陷。
1. 分析任务：修复主角动机断裂
2. 原文本分析：对话缺乏潜台词
角色：沈砚，男主，隐忍克制。
目标：强化动机铺垫。
限制：不增删情节。
"""

# 模型返回 JSON 回包而非正文的典型形态（应被守卫拦下）
JSON_GARBAGE = json.dumps(
    {
        "analysis": "chapter reviewed and fixed",
        "violations_fixed": ["timeline", "character state"],
        "status": "ok",
    },
    ensure_ascii=False,
)


class _RecordingLLM:
    """记录调用参数的 LLM 桩，统一覆盖 generate / get_llm_response / get_optimize_llm_response。"""

    generate_structured = LLMService.generate_structured

    def __init__(self, response: str):
        self.response = response
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return self.response

    async def get_llm_response(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    async def get_optimize_llm_response(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _ReviewHarness(PipelineReviewMixin):
    def __init__(self, response: str):
        self.llm_service = _RecordingLLM(response)


class _DummyPromptService:
    def __init__(self, prompt: str):
        self.prompt = prompt

    async def get_prompt(self, _name: str):
        return self.prompt


def _make_consistency_service(response: str) -> ConsistencyService:
    service = ConsistencyService(db=None, llm_service=_RecordingLLM(response))

    async def _fake_context(project_id, include_foreshadowing=True):
        return {}

    service._get_check_context = _fake_context
    return service


def _critical_violations():
    return [
        ConsistencyViolation(
            severity=ViolationSeverity.CRITICAL,
            category="plot",
            description="时间线冲突",
        )
    ]


# ---------------------------------------------------------------------------
# consistency auto_fix
# ---------------------------------------------------------------------------

def test_auto_fix_rejects_json_garbage():
    service = _make_consistency_service(JSON_GARBAGE)

    fixed = asyncio.run(service.auto_fix("p1", CHAPTER_BODY, _critical_violations(), user_id=1))

    assert fixed is None


def test_auto_fix_rejects_too_short_text():
    service = _make_consistency_service("已修复。")

    fixed = asyncio.run(service.auto_fix("p1", CHAPTER_BODY, _critical_violations(), user_id=1))

    assert fixed is None


def test_auto_fix_accepts_valid_chapter_and_passes_timeout():
    service = _make_consistency_service(CHAPTER_BODY)

    fixed = asyncio.run(service.auto_fix("p1", CHAPTER_BODY, _critical_violations(), user_id=1))

    assert fixed == CHAPTER_BODY
    assert service.llm_service.calls[0]["timeout"] == 180.0


def test_check_consistency_passes_timeout():
    service = _make_consistency_service(
        json.dumps({"is_consistent": True, "violations": [], "summary": "ok"})
    )

    asyncio.run(service.check_consistency("p1", CHAPTER_BODY, user_id=1))

    assert service.llm_service.calls[0]["timeout"] == 180.0


def test_run_consistency_check_keeps_chapter_when_auto_fix_rejected(monkeypatch):
    """消费端回归：auto_fix 守卫拒绝后，_run_consistency_check 保留原章节。"""
    harness = _ReviewHarness(JSON_GARBAGE)
    harness.session = None

    async def _fake_check(self, project_id, chapter_text, user_id, include_foreshadowing=True, entity_registry_info=None):
        return ConsistencyCheckResult(
            is_consistent=False,
            violations=_critical_violations(),
            summary="发现严重冲突",
        )

    async def _fake_context(self, project_id, include_foreshadowing=True):
        return {}

    monkeypatch.setattr(ConsistencyService, "check_consistency", _fake_check)
    monkeypatch.setattr(ConsistencyService, "_get_check_context", _fake_context)

    content, report = asyncio.run(
        harness._run_consistency_check(project_id="p1", chapter_text=CHAPTER_BODY, user_id=1)
    )

    assert content == CHAPTER_BODY
    assert report["auto_fix_applied"] is False


# ---------------------------------------------------------------------------
# combined_revision
# ---------------------------------------------------------------------------

def test_combined_revision_rejects_analysis_text():
    harness = _ReviewHarness("修订说明：" + ANALYSIS_OUTPUT)

    content, report = asyncio.run(
        harness._run_combined_revision(
            CHAPTER_BODY,
            critical_flaws=["主角动机断裂"],
            refinement_suggestions="补铺垫",
            enable_self_critique=True,
            chapter_mission=None,
            user_id=1,
        )
    )

    assert content == CHAPTER_BODY
    assert report["applied"] is False
    assert report["reason"] == "revision_unavailable"


def test_combined_revision_rejects_too_short_result():
    original = CHAPTER_BODY * 3
    harness = _ReviewHarness(CHAPTER_BODY)  # 有效正文但不足原文一半

    content, report = asyncio.run(
        harness._run_combined_revision(
            original,
            critical_flaws=["节奏拖沓"],
            refinement_suggestions="",
            enable_self_critique=False,
            chapter_mission=None,
            user_id=1,
        )
    )

    assert content == original
    assert report["applied"] is False
    assert report["reason"] == "revision_unavailable"


def test_combined_revision_accepts_valid_local_plan():
    harness = _ReviewHarness(json.dumps({
        "emotional_review": {"summary": "保留未寄出的信，只改一个动词。", "issues": [], "protected_passages": []},
        "edits": [{"before": "沈砚推开窗", "after": "沈砚支起窗", "reason": "动作具体"}],
    }, ensure_ascii=False))

    content, report = asyncio.run(
        harness._run_combined_revision(
            CHAPTER_BODY,
            critical_flaws=["节奏拖沓"],
            refinement_suggestions="",
            enable_self_critique=False,
            chapter_mission=None,
            user_id=1,
        )
    )

    assert content == CHAPTER_BODY.replace("沈砚推开窗", "沈砚支起窗")
    assert report["applied"] is True


# ---------------------------------------------------------------------------
# enrichment
# ---------------------------------------------------------------------------

def test_enrichment_rejects_non_chapter_output():
    service = EnrichmentService(db=None, llm_service=_RecordingLLM(ANALYSIS_OUTPUT))

    result = asyncio.run(
        service.check_and_enrich(chapter_text=CHAPTER_BODY, target_word_count=1000, user_id=1)
    )

    assert result is None
    assert service.llm_service.calls[0]["timeout"] == 180.0


def test_enrichment_rejects_too_short_result():
    original = CHAPTER_BODY * 4
    service = EnrichmentService(db=None, llm_service=_RecordingLLM(CHAPTER_BODY))

    result = asyncio.run(
        service.check_and_enrich(chapter_text=original, target_word_count=1000, user_id=1)
    )

    assert result is None


def test_enrichment_accepts_valid_chapter():
    enriched_body = CHAPTER_BODY * 3
    service = EnrichmentService(db=None, llm_service=_RecordingLLM(enriched_body))

    result = asyncio.run(
        service.check_and_enrich(chapter_text=CHAPTER_BODY, target_word_count=1000, user_id=1)
    )

    assert result is not None
    assert result.enriched_content == enriched_body


# ---------------------------------------------------------------------------
# humanize
# ---------------------------------------------------------------------------

def _make_humanization_service(response: str) -> HumanizationService:
    service = HumanizationService.__new__(HumanizationService)
    service.session = None
    service.llm_service = _RecordingLLM(response)
    service.prompt_service = _DummyPromptService("扫描报告：{{scan_report}}\n原文：{{original_text}}")
    return service


def test_humanize_rejects_non_chapter_output():
    service = _make_humanization_service(ANALYSIS_OUTPUT)
    report = service.scan(CHAPTER_BODY)

    result = asyncio.run(service.humanize(CHAPTER_BODY, report, user_id=1))

    assert result == CHAPTER_BODY


def test_humanize_accepts_valid_chapter():
    service = _make_humanization_service(CHAPTER_BODY)
    report = service.scan(CHAPTER_BODY)

    result = asyncio.run(service.humanize(CHAPTER_BODY, report, user_id=1))

    assert result == CHAPTER_BODY


# ---------------------------------------------------------------------------
# optimizer prompt f-string 转义回归
# ---------------------------------------------------------------------------

def test_optimizer_prompt_renders_single_brace_json_example():
    response = json.dumps(
        {"optimized_content": CHAPTER_BODY, "optimization_notes": "综合优化完成"},
        ensure_ascii=False,
    )
    harness = _ReviewHarness(response)

    content, _report = asyncio.run(harness._run_optimizer("原文", user_id=1))

    prompt = harness.llm_service.calls[0]["conversation_history"][0]["content"]
    assert "{{" not in prompt
    assert '{\n  "optimized_content"' in prompt
    assert content == CHAPTER_BODY


def test_auto_fix_truncated_response_keeps_original():
    """后处理步输出被截断（fail_on_truncation=True → 抛 LLMResponseTruncated）时走异常兜底，保留原文。"""
    from app.services.llm_service import LLMResponseTruncated

    service = _make_consistency_service(CHAPTER_BODY)

    async def _truncating_generate(prompt, **kwargs):
        service.llm_service.calls.append({"prompt": prompt, **kwargs})
        raise LLMResponseTruncated("半截修复文本")

    service.llm_service.generate = _truncating_generate

    fixed = asyncio.run(service.auto_fix("p1", CHAPTER_BODY, _critical_violations(), user_id=1))

    assert fixed is None
    assert service.llm_service.calls[0]["fail_on_truncation"] is True
