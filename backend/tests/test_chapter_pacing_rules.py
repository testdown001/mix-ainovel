"""Quiet chapters must retain their purpose through planning and runtime guidance."""
import json
import re
from pathlib import Path

import pytest

from app.core.constants import ALL_HARD_RULES
from app.services.context_planner_service import ContextPlannerService, ContextStrategy
from app.services.genre_profile_service import GenreProfileService
from app.services.humanization_service import HumanizationService
from app.services.narrative_variety_tracker import ChapterPattern, NarrativeVarietyTracker
from app.services.platinum_writing_context import build_hook_continuity_brief, build_platinum_rhythm_brief
from app.services.strand_weave_service import StrandWeaveService


PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


@pytest.mark.parametrize("filename", [
    "writing.md", "writing_v2.md", "writing_v3.md", "writing_fast.md",
    "chapter_plan.md", "chapter_plan_lite.md", "platinum_writing_brief.md",
])
def test_writer_and_director_templates_do_not_reintroduce_uniform_quotas(filename):
    content = (PROMPTS / filename).read_text(encoding="utf-8")
    for obsolete_rule in (
        "600-900", "35-55%", "每 1000 字至少 1", "禁止一章内闭环",
        "至少 1 处趣味点", "结尾必须刀切",
    ):
        assert obsolete_rule not in content, (filename, obsolete_rule)
    assert "章节功能" in content
    assert "余波" in content
    assert "局部" in content


def test_director_examples_remain_compatible_with_existing_mission_protocol():
    full = json.loads(re.search(r"```json\s*(.*?)\s*```", (PROMPTS / "chapter_plan.md").read_text(encoding="utf-8"), re.S)[1])
    lite = json.loads(re.search(r"```json\s*(.*?)\s*```", (PROMPTS / "chapter_plan_lite.md").read_text(encoding="utf-8"), re.S)[1])
    assert full["hard_constraints"]["macro_beat"] == lite["macro_beat"] == "E|F|P|C"
    assert {"emotion_curve", "deliberate_omission", "tone_guide"} <= full["soft_suggestions"].keys()
    assert "relationship_temp" in full["scene_list"][0]
    assert isinstance(lite["ending_hook"], dict)


@pytest.mark.parametrize("filename", ["screenwriting_outline.md", "outline_generation.md", "blueprint_review.md"])
def test_outline_and_review_allow_local_resolution_and_aftermath(filename):
    content = (PROMPTS / filename).read_text(encoding="utf-8")
    for obsolete_rule in ("置空视为节奏事故", "不许置空", "最后一章必须是硬钩子", "批次最后一章必须硬收尾", "每晚一章扣一档", "禁止节奏平铺，没有阶段性爆点"):
        assert obsolete_rule not in content
    assert "章节功能" in content and "局部" in content and "余波" in content


def test_version_review_judges_chapter_function_instead_of_coolpoint_quotas():
    content = (PROMPTS / "editor_review.md").read_text(encoding="utf-8")
    for obsolete_rule in ("每章必须≥1", "30/40/30", "压3扬7", "爽点KPI"):
        assert obsolete_rule not in content
    assert "章节功能、情绪走向、松弛点和留白" in content
    assert "不因安静、少对白、没有笑点或局部闭环而扣分" in content
    example = json.loads(re.search(r"```json\s*(.*?)\s*```", content, re.S)[1])
    assert {"best_version_index", "scores", "overall_evaluation", "critical_flaws", "refinement_suggestions", "final_recommendation"} <= example.keys()


@pytest.mark.parametrize("phase", ["setup", "rising", "climax", "resolution"])
def test_compiled_fallback_scene_plan_respects_quiet_chapter_design(phase):
    scenes = ContextPlannerService()._build_scene_plan(
        chapter_phase=phase, outline_title="旧碗", outline_summary="两人收拾遗物，在沉默中重新靠近",
        writing_notes="保留余波", character_names=["林玄", "师姐"], target_words=3000,
        skill_policies=[], context_strategy=ContextStrategy(mode="rag_balanced", reason="test", query_limit=2),
    )
    rendered = "\n".join(f"{scene.goal}\n{scene.conflict}" for scene in scenes)
    assert "两人收拾遗物，在沉默中重新靠近" in rendered
    for obsolete_rule in ("当前危机", "正面碰撞", "压出新的问题", "制造选择压力"):
        assert obsolete_rule not in rendered
    assert all(not scene.conflict for scene in scenes)
    assert sum(scene.target_words for scene in scenes) == 3000


def test_runtime_guidance_preserves_nested_aftermath_function_and_resolved_ending():
    mission = {
        "hard_constraints": {"chapter_type": "余波章", "pov": "林玄", "chapter_end_style": "告别完成后的余韵"},
        "chapter_type": "高潮章",  # 旧顶层值不能覆盖正式规划。
    }
    rhythm = build_platinum_rhythm_brief(
        chapter_number=80, total_chapters=100, outline_title="旧碗", outline_summary="整理遗物",
        chapter_mission=mission, genre_pacing_config={"max_buildup_chapters": 1},
    )
    hook = build_hook_continuity_brief(previous_summary="告别已经结束", previous_tail="他收好了旧碗。", chapter_mission=mission)
    assert "本章功能：余波章" in rhythm
    assert "本章功能：高潮章" not in rhythm
    assert "告别完成后的余韵" in hook
    assert "中段加压：至少出现一次" not in hook
    assert "后必须出爆点" not in rhythm
    assert "局部闭环" in hook


def test_genre_and_strand_do_not_override_chapter_function_with_quotas():
    profile = {
        "name": "测试题材", "hook_config": {"opening_hook_mandatory": True, "min_hooks_per_chapter": 3},
        "coolpoint_config": {"interval": 1}, "micropayoff_config": {"per_chapter_min": 3},
    }
    genre = GenreProfileService.build_genre_prompt_injection(profile)
    for obsolete_rule in ("开头钩子必须存在", "每章至少", "每 1 章至少"):
        assert obsolete_rule not in genre
    assert "本章功能" in genre
    strand = StrandWeaveService.build_strand_prompt(StrandWeaveService(10).plan_strands()[0])
    assert "以本章规划为准" in strand
    assert "每章至少一个里程碑" not in strand
    assert "对话比例由本章功能" in ALL_HARD_RULES
    assert "每条线每章至少推进一次" not in ALL_HARD_RULES


def test_low_dialogue_history_does_not_force_dialogue_into_solitary_scenes():
    patterns = [ChapterPattern(chapter_number=n, dialogue_ratio=0.02) for n in (1, 2, 3)]
    guidance = NarrativeVarietyTracker.analyze_variety(patterns, 4)["dialogue_variety"]
    assert "本章需要更多对话驱动" not in guidance
    assert "无需为比例添加对白" in guidance


def test_humanization_does_not_penalize_complete_sentences_or_no_dialogue():
    # 十余个完整句、无对白/残句；旧扫描器仅凭这些特征便会扣人味分。
    text = "\n".join([
        "他把药盒放回柜子，盒底还压着去年写的方子。", "布鞋晾在檐下，鞋底的泥已经干了。",
        "桌上留了半碗水，他端起来浇了花。", "账本翻到月底，那一页还没有记完。",
        "门边的伞歪着，他重新摆正。", "米缸见了底，明日该再去买些。",
        "他将一张收条叠好，夹进书中。", "师姐送来的饭还温着，他吃了一口。",
        "旧碗缺了一角，他另找了块布包好。", "他写下回信，把日期改成明天。",
        "椅子挪到了门边，恰好留出两人坐的位置。", "钥匙收进衣袋，他带上了门。",
    ])
    service = HumanizationService.__new__(HumanizationService)
    report = service.scan(text)
    assert report.missing_human_deduction == 0
    assert not {"low_dialogue", "no_incomplete_sentences"} & {issue.category for issue in report.issues}
    explanatory = service.scan("因为他迟到了，所以只好等候。这意味着时间不够，也就是说需要改期。" * 12)
    assert any(issue.category == "over_explanation" for issue in explanatory.issues)
