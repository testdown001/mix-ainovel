"""Literary 分支加固回归测试（审计 P1 #21/#22 残留 + P1-9）。

1. 场景循环通用容错：单场景异常重试一次，仍失败以空场景继续拼章并在
   metadata.missing_scenes 记录；全部场景失败才整章失败。
2. literary 分支时间预算：deadline 越界时后处理步(雕塑/金句/人味化/扩写/质检)
   被跳过并记 review_summaries['time_budget']；场景生成本体不受预算约束。
3. 场景 2+ 硬约束不丢：forbidden_characters/POV/章节目标以固定段每场景完整
   携带，不再被 compress_context 头部截断吃掉。
"""
import asyncio
import time
from types import SimpleNamespace

import pytest

from app.services.literary_generation_flow_service import (
    LiteraryGenerationFlowResult,
    LiteraryGenerationFlowService,
)
from app.services.scene_generation_service import SceneGenerationService


class _Guardrails:
    def check(self, **kwargs):
        return SimpleNamespace(passed=True)

    def apply_local_patches(self, text, result):
        return text


class _Policy:
    def resolve_temperature(self, chapter_mission):
        return 0.7


class _Compression:
    async def compress_overlength(self, text, *, target_max, user_id):
        return text[:target_max]

    @staticmethod
    def hard_trim_to_limit(text, limit):
        return text[:limit]


def _scene_service(llm) -> SceneGenerationService:
    return SceneGenerationService(llm, _Guardrails(), _Policy(), _Compression())


_MISSION_3_SCENES = {
    "pov": "林峰",
    "scene_list": [
        {"goal": "开场", "target_words": 300},
        {"goal": "冲突", "target_words": 300},
        {"goal": "收束", "target_words": 300},
    ],
}


def _run_scenes(service, prompt_sections_data=None, chapter_mission=_MISSION_3_SCENES):
    return asyncio.run(
        service.generate_scene_by_scene(
            prompt_sections_data=prompt_sections_data or {"chapter_goals": "[当前章节目标]\n标题：破阵"},
            writer_prompt="写作",
            chapter_mission=chapter_mission,
            forbidden_characters=[],
            allowed_new_characters=[],
            user_id=1,
        )
    )


# ---------- 1) 场景循环通用容错 ----------


def test_scene_failure_retries_once_then_continues_with_missing_scene():
    class _LLM:
        def __init__(self):
            self.calls: list[str] = []

        async def get_llm_response(self, **kwargs):
            prompt = kwargs["conversation_history"][0]["content"]
            self.calls.append(prompt)
            if "场景 2/3" in prompt:
                raise TimeoutError("上游超时")
            return "场景正文，江面起了雾。"

    llm = _LLM()
    result = _run_scenes(_scene_service(llm))

    # 场景2：首次失败 + 重试一次 = 2 次调用；场景1/3 各 1 次 → 共 4 次
    scene2_attempts = [p for p in llm.calls if "场景 2/3" in p]
    assert len(scene2_attempts) == 2
    assert len(llm.calls) == 4
    # 整章完成：场景1/3 正常拼章，场景2 缺失并记录
    assert result["content"] == "场景正文，江面起了雾。\n\n场景正文，江面起了雾。"
    assert result["metadata"]["missing_scenes"] == [2]


def test_scene_empty_output_recorded_as_missing():
    class _LLM:
        async def get_llm_response(self, **kwargs):
            prompt = kwargs["conversation_history"][0]["content"]
            if "场景 3/3" in prompt:
                return ""
            return "场景正文，钟声敲了三下。"

    result = _run_scenes(_scene_service(_LLM()))

    assert result["metadata"]["missing_scenes"] == [3]
    assert "场景正文" in result["content"]


def test_all_scenes_fail_raises_chapter_failure():
    class _LLM:
        def __init__(self):
            self.call_count = 0

        async def get_llm_response(self, **kwargs):
            self.call_count += 1
            raise RuntimeError("5xx")

    llm = _LLM()
    with pytest.raises(RuntimeError, match="全部"):
        _run_scenes(_scene_service(llm))
    # 每场景重试一次：3 场景 × 2 次
    assert llm.call_count == 6


# ---------- 3) 场景 2+ 硬约束不丢（P1-9） ----------


def test_scene3_prompt_carries_full_hard_constraints():
    class _LLM:
        def __init__(self):
            self.calls: list[str] = []

        async def get_llm_response(self, **kwargs):
            self.calls.append(kwargs["conversation_history"][0]["content"])
            return "场景正文，江面起了雾。"

    llm = _LLM()
    service = _scene_service(llm)
    # 大体量叙事上下文：修复前场景2+ 的 core_context 被 compress_context(1500) 头部
    # 截断，拼接序列尾部的 forbidden_characters/blueprint 约束彻底消失
    prompt_sections_data = {
        "chapter_goals": "[当前章节目标]\n标题：破阵",
        "story_skeleton": "骨" * 1800,
        "previous_summary": "前" * 1800,
        "writer_blueprint": "蓝图内容",
        "forbidden_characters": "李逆天, 王魔尊",
    }
    _run_scenes(service, prompt_sections_data=prompt_sections_data)

    assert len(llm.calls) == 3
    scene3_prompt = llm.calls[2]
    # 硬约束固定段每场景完整携带
    assert "李逆天" in scene3_prompt
    assert "王魔尊" in scene3_prompt
    assert "严禁在本章出现" in scene3_prompt
    assert "本章视角(POV)：林峰" in scene3_prompt
    assert "[当前章节目标]" in scene3_prompt
    # 叙事性上下文仍走压缩路径
    assert "[精简上下文]" in scene3_prompt


# ---------- 2) literary 分支时间预算 ----------


def _literary_service(scene_service, profile):
    return LiteraryGenerationFlowService(
        session=SimpleNamespace(),
        llm_service=SimpleNamespace(),
        scene_generation_service=scene_service,
        generation_policy_service=SimpleNamespace(
            resolve_literary_postprocess_profile=lambda **kwargs: profile
        ),
        text_compression_service=_Compression(),
        guardrails=_Guardrails(),
    )


def _run_literary(service, *, deadline, run_enrichment, run_quality_detection, stages=None):
    return asyncio.run(
        service.run(
            voice_samples_task=None,
            context_plan=SimpleNamespace(),
            prompt_compiler=SimpleNamespace(
                compile_scene_prompt_data=lambda **kwargs: kwargs["prompt_sections_data"]
            ),
            prompt_sections_data={"chapter_goals": "目标"},
            writer_prompt="writer",
            chapter_mission={"pov": "林峰"},
            forbidden_characters=[],
            allowed_new_characters=[],
            user_id=1,
            genre_profile=None,
            chapter_word_count_max=3000,
            chapter_target_word_count=2000,
            chapter_word_count_min=1000,
            config=SimpleNamespace(
                enable_six_dimension=False,
                enable_anti_hallucination=False,
                humanization_threshold=70,
            ),
            outline_title="标题",
            history_context={"previous_summary": "上章", "completed_chapters": []},
            project_id="proj-1",
            chapter_number=5,
            enhanced_context={},
            run_enrichment=run_enrichment,
            run_quality_detection=run_quality_detection,
            mark_stage=(lambda name, started: stages.append(name)) if stages is not None else None,
            deadline=deadline,
        )
    )


def test_literary_budget_exhausted_skips_postprocessing_not_scene_generation():
    scene_calls: list[str] = []

    class _SceneService:
        async def generate_scene_by_scene(self, **kwargs):
            scene_calls.append("scene")
            return {"content": "正文", "metadata": {}}

    postproc_calls: list[str] = []

    async def _run_enrichment(content, **kwargs):
        postproc_calls.append("enrichment")
        return content + "·扩", {"applied": True}

    async def _run_quality_detection(content, **kwargs):
        postproc_calls.append("quality_detection")
        return {"overall_score": 90}

    # 全部后处理开关开启 + 预算已耗尽：llm_service 为空桩，任何一步真跑都会炸
    service = _literary_service(
        _SceneService(),
        {
            "enable_prose_sculpting": True,
            "enable_golden_paragraph": True,
            "enable_humanization": True,
        },
    )
    stages: list[str] = []
    result = _run_literary(
        service,
        deadline=time.perf_counter() - 1,
        run_enrichment=_run_enrichment,
        run_quality_detection=_run_quality_detection,
        stages=stages,
    )

    assert isinstance(result, LiteraryGenerationFlowResult)
    # 场景生成本体不受预算约束（正文优先）
    assert scene_calls == ["scene"]
    assert "generate_scene_by_scene" in stages
    # 后处理全部被跳过、正文原样返回
    assert postproc_calls == []
    assert result.best_content == "正文"
    assert result.review_summaries["time_budget"]["skipped"] == [
        "prose_sculpting",
        "golden_paragraph",
        "humanization",
        "enrichment",
        "quality_detection",
    ]


def test_literary_no_deadline_runs_postprocessing():
    class _SceneService:
        async def generate_scene_by_scene(self, **kwargs):
            return {"content": "正文", "metadata": {}}

    postproc_calls: list[str] = []

    async def _run_enrichment(content, **kwargs):
        postproc_calls.append("enrichment")
        return content, None

    async def _run_quality_detection(content, **kwargs):
        postproc_calls.append("quality_detection")
        return {"overall_score": 85}

    service = _literary_service(
        _SceneService(),
        {
            "enable_prose_sculpting": False,
            "enable_golden_paragraph": False,
            "enable_humanization": False,
        },
    )
    result = _run_literary(
        service,
        deadline=None,
        run_enrichment=_run_enrichment,
        run_quality_detection=_run_quality_detection,
    )

    assert postproc_calls == ["enrichment", "quality_detection"]
    assert "time_budget" not in result.review_summaries
    assert result.review_summaries["quality_detection"]["overall_score"] == 85


def test_orchestrator_literary_branch_passes_deadline():
    """orchestrator 装配回归：literary 分支必须把预算 deadline 传给流程服务
    （防止 kwarg 被误删导致 literary 再次退回无预算状态）。"""
    import inspect

    from app.services import pipeline_orchestrator as po

    src = inspect.getsource(po.PipelineOrchestrator)
    literary_idx = src.index("literary_generation_flow_service.run(")
    standard_idx = src.index("standard_generation_flow_service.run(")
    assert "deadline=literary_deadline" in src[literary_idx:standard_idx]
