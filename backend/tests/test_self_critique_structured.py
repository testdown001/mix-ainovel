"""self_critique 接入 generate_structured 后的行为锁定（此前该服务无测试）。

验证：合法 JSON → 返回带 weight 的 dict；非法输出 → 走 default 回退仍返回结构完整 dict。
"""
import asyncio

from app.services.llm_service import LLMService
from app.services.self_critique_service import (
    SelfCritiqueService,
    CritiqueDimension,
)


def _make_service(raw_responses):
    llm = LLMService.__new__(LLMService)  # 跳过 __init__
    queue = list(raw_responses)

    async def _fake_generate(*args, **kwargs):
        return queue.pop(0)

    llm.generate = _fake_generate  # type: ignore[attr-defined]
    return SelfCritiqueService(db=None, llm_service=llm, prompt_service=None)


def test_critique_valid_json_returns_structured_dict():
    svc = _make_service([
        '{"dimension":"logic","overall_score":82,'
        '"issues":[{"severity":"major","problem":"时间线矛盾","suggestion":"调整顺序"}],'
        '"strengths":["节奏紧凑"],"summary":"整体良好"}'
    ])
    result = asyncio.run(
        svc.critique_chapter(chapter_content="正文……", dimension=CritiqueDimension.LOGIC)
    )
    assert result["overall_score"] == 82
    assert result["dimension"] == "logic"
    assert result["issues"][0]["severity"] == "major"
    assert "weight" in result  # 维度权重已附加


def test_critique_garbage_falls_back_to_default():
    # 两次都非法 → generate_structured 用 default 回退，仍返回结构完整 dict（不崩、不缺键）
    svc = _make_service(["完全不是JSON", "还是垃圾"])
    result = asyncio.run(
        svc.critique_chapter(chapter_content="正文……", dimension=CritiqueDimension.WRITING)
    )
    assert result["dimension"] == "writing"
    assert result["overall_score"] == 70
    assert result["issues"] == []
    assert "weight" in result
