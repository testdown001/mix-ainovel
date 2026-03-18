import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.context_planner_service import ContextPlan, EvidenceItem, GenerationEvidencePack
from app.services.evidence_grader_service import EvidenceGraderService


def _make_plan(*, is_fast_path=False, core_goal="推进主线冲突", chapter_phase="development"):
    return ContextPlan.from_dict({
        "intent": {"core_goal": core_goal},
        "chapter_phase": chapter_phase,
        "retrieval_tasks": [
            {"task_id": "local_plot", "source": "local_plot_rag", "mode": "vector", "query_template": "{outline_title}"},
        ],
        "skill_policies": [],
        "prompt_modules": ["chapter_goal"],
        "verification_tasks": ["continuity_check"],
        "budgets": {},
        "is_fast_path": is_fast_path,
        "metadata": {},
    })


def _make_evidence_pack():
    pack = GenerationEvidencePack()
    pack.local_plot.append(
        EvidenceItem(source="local_plot_rag", title="剧情片段 1", content="主角与敌人对峙", score=0.7)
    )
    pack.local_plot.append(
        EvidenceItem(source="local_plot_rag", title="剧情片段 2", content="无关内容：天气预报", score=0.3)
    )
    pack.global_arc.append(
        EvidenceItem(source="global_arc_rag", title="上一章摘要", content="上一章中主角得知决战情报", score=0.7)
    )
    pack.symbolic_items.append(
        EvidenceItem(source="symbolic_rag", title="伏笔", content="黑玉碎片的来源", score=0.9)
    )
    return pack


def _mock_llm_service(*, grader_configured=True, response_json=None, raise_error=False):
    """创建 mock LLMService。"""
    default_response = json.dumps([
        {"index": 0, "score": 0.9, "reason": "直接相关主线冲突"},
        {"index": 1, "score": 0.15, "reason": "与本章无关"},
        {"index": 2, "score": 0.8, "reason": "提供上文脉络"},
        {"index": 3, "score": 0.95, "reason": "伏笔需要回收"},
    ])

    llm = SimpleNamespace()

    if grader_configured:
        llm._resolve_grader_llm_config = AsyncMock(return_value={
            "api_key": "test-key",
            "base_url": "http://test",
            "model": "test-haiku",
            "api_format": None,
        })
    else:
        llm._resolve_grader_llm_config = AsyncMock(return_value=None)

    if raise_error:
        llm.get_grader_llm_response = AsyncMock(side_effect=Exception("LLM 调用失败"))
    else:
        llm.get_grader_llm_response = AsyncMock(return_value=response_json or default_response)

    return llm


def test_grade_skips_on_fast_path():
    """fast_path 模式下跳过评分。"""
    plan = _make_plan(is_fast_path=True)
    pack = _make_evidence_pack()
    llm = _mock_llm_service()
    grader = EvidenceGraderService(llm)

    result = asyncio.run(grader.grade(evidence_pack=pack, plan=plan))

    assert result["graded"] is False
    assert result["reason"] == "fast_path"
    llm._resolve_grader_llm_config.assert_not_called()


def test_grade_skips_when_grader_not_configured():
    """LLM grader 配置缺失时优雅跳过。"""
    plan = _make_plan()
    pack = _make_evidence_pack()
    llm = _mock_llm_service(grader_configured=False)
    grader = EvidenceGraderService(llm)

    result = asyncio.run(grader.grade(evidence_pack=pack, plan=plan))

    assert result["graded"] is False
    assert result["reason"] == "grader_not_configured"


def test_grade_scores_all_items():
    """正常评分流程，验证分数写回 EvidenceItem。"""
    plan = _make_plan()
    pack = _make_evidence_pack()
    llm = _mock_llm_service()
    grader = EvidenceGraderService(llm)

    result = asyncio.run(grader.grade(evidence_pack=pack, plan=plan))

    assert result["graded"] is True
    assert result["total"] == 4
    assert len(result["scores"]) == 4

    # 验证分数写回了 EvidenceItem.metadata
    assert pack.local_plot[0].metadata["grader_score"] == 0.9
    assert pack.local_plot[1].metadata["grader_score"] == 0.15
    assert pack.global_arc[0].metadata["grader_score"] == 0.8
    assert pack.symbolic_items[0].metadata["grader_score"] == 0.95


def test_grade_filters_low_score_items():
    """低于阈值的 items 被标记 graded_out。"""
    plan = _make_plan()
    pack = _make_evidence_pack()
    llm = _mock_llm_service()
    grader = EvidenceGraderService(llm)

    result = asyncio.run(grader.grade(evidence_pack=pack, plan=plan, threshold=0.3))

    assert result["filtered"] == 1
    # 低分项被标记
    assert pack.local_plot[1].metadata.get("graded_out") is True
    # 高分项未被标记
    assert pack.local_plot[0].metadata.get("graded_out") is None


def test_grade_retries_on_failure():
    """LLM 调用失败时重试一次，仍失败则优雅降级。"""
    plan = _make_plan()
    pack = _make_evidence_pack()
    llm = _mock_llm_service(raise_error=True)
    grader = EvidenceGraderService(llm)

    result = asyncio.run(grader.grade(evidence_pack=pack, plan=plan, max_retries=1))

    assert result["graded"] is False
    assert result["reason"] == "grader_call_failed"
    # 默认 1 次 + 1 次重试 = 2 次调用
    assert llm.get_grader_llm_response.call_count == 2


def test_grade_handles_malformed_json():
    """LLM 返回非法 JSON 时不崩溃。"""
    plan = _make_plan()
    pack = _make_evidence_pack()
    llm = _mock_llm_service(response_json="这不是有效的 JSON 格式")
    grader = EvidenceGraderService(llm)

    result = asyncio.run(grader.grade(evidence_pack=pack, plan=plan))

    assert result["graded"] is False
    assert result["reason"] == "grader_call_failed"


def test_grade_skips_on_empty_evidence():
    """空证据包时跳过评分。"""
    plan = _make_plan()
    pack = GenerationEvidencePack()
    llm = _mock_llm_service()
    grader = EvidenceGraderService(llm)

    result = asyncio.run(grader.grade(evidence_pack=pack, plan=plan))

    assert result["graded"] is False
    assert result["reason"] == "no_evidence_items"


def test_grade_clamps_scores_to_valid_range():
    """评分超出 0-1 范围时自动截断。"""
    plan = _make_plan()
    pack = GenerationEvidencePack()
    pack.local_plot.append(
        EvidenceItem(source="local_plot_rag", title="片段", content="内容", score=0.5)
    )

    response = json.dumps([{"index": 0, "score": 1.5, "reason": "超高分"}])
    llm = _mock_llm_service(response_json=response)
    grader = EvidenceGraderService(llm)

    result = asyncio.run(grader.grade(evidence_pack=pack, plan=plan))

    assert result["graded"] is True
    assert pack.local_plot[0].metadata["grader_score"] == 1.0


def test_grade_custom_threshold():
    """自定义阈值生效。"""
    plan = _make_plan()
    pack = _make_evidence_pack()
    llm = _mock_llm_service()
    grader = EvidenceGraderService(llm)

    result = asyncio.run(grader.grade(evidence_pack=pack, plan=plan, threshold=0.85))

    # 0.9, 0.15, 0.8, 0.95 — 低于 0.85 的有 2 个 (0.15, 0.8)
    assert result["filtered"] == 2
    assert result["threshold"] == 0.85
