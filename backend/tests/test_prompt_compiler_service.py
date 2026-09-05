from app.services.context_planner_service import ContextPlan
from app.services.prompt_compiler_service import PromptCompilerService


def test_prompt_compiler_filters_sections_and_adds_skill_section():
    service = PromptCompilerService()
    plan = ContextPlan.from_dict(
        {
            "intent": {"core_goal": "推进线索"},
            "chapter_phase": "development",
            "retrieval_tasks": [],
            "skill_policies": [
                {
                    "skill_id": "dialogue_polish",
                    "phase": "pre_prompt",
                    "params": {"intensity": "strong"},
                    "retrieval_hints": ["历史对白样本"],
                    "prompt_hints": ["对白风格差异化"],
                    "verify_hints": ["对白漂移检查"],
                }
            ],
            "prompt_modules": [
                "chapter_goal",
                "mission_brief",
                "world_blueprint",
                "skill_instructions",
                "hard_constraints",
            ],
            "verification_tasks": [],
            "budgets": {},
            "is_fast_path": False,
            "metadata": {},
        }
    )

    sections, summary = service.compile(
        plan=plan,
        sections=[
            ("[当前章节目标]", "目标"),
            ("[创作任务书](本章写作的核心执行指南，必须严格遵循)", "任务书"),
            ("[上一章摘要]", "上一章"),
            ("[世界蓝图](JSON，已裁剪)", "蓝图"),
            ("[写作硬性约束](必须严格遵守)", "约束"),
        ],
    )

    titles = [title for title, _ in sections]
    assert "[上一章摘要]" not in titles
    assert "[技能策略指令]" in titles
    assert "[当前章节目标]" in titles
    assert summary["section_count_before"] == 5
    assert summary["section_count_after"] == 5
    assert "[上一章摘要]" in summary["dropped_sections"]


def test_prompt_compiler_filters_scene_prompt_data():
    service = PromptCompilerService()
    plan = ContextPlan.from_dict(
        {
            "intent": {},
            "chapter_phase": "climax",
            "retrieval_tasks": [],
            "skill_policies": [],
            "prompt_modules": ["chapter_goal", "world_blueprint"],
            "verification_tasks": [],
            "budgets": {},
            "is_fast_path": False,
            "metadata": {},
        }
    )

    compiled = service.compile_scene_prompt_data(
        plan=plan,
        prompt_sections_data={
            "chapter_goals": "目标",
            "mission_brief": "任务书",
            "previous_summary": "上一章",
            "writer_blueprint": "蓝图",
            "reference_prose": "范文",
            "reference_guidance": "统一声音、兑现与余波",
            "reference_beats": "适用于本章的伏笔回收",
        },
    )

    assert compiled["chapter_goals"] == "目标"
    assert compiled["writer_blueprint"] == "蓝图"
    assert "mission_brief" not in compiled
    assert "previous_summary" not in compiled
    assert compiled["reference_prose"] == "范文"
    assert compiled["reference_guidance"] == "统一声音、兑现与余波"
    assert compiled["reference_beats"] == "适用于本章的伏笔回收"


def test_prompt_compiler_keeps_confirmed_creative_memory_for_scene_generation():
    service = PromptCompilerService()
    plan = ContextPlan.from_dict(
        {
            "intent": {},
            "chapter_phase": "development",
            "prompt_modules": ["creative_memory"],
        }
    )

    compiled = service.compile_scene_prompt_data(
        plan=plan,
        prompt_sections_data={"creative_memory": "[已确认创作记忆] 保持限知视角"},
    )

    assert compiled["creative_memory"] == "[已确认创作记忆] 保持限知视角"
