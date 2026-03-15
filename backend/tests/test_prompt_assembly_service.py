from types import SimpleNamespace

from app.services.prompt_assembly_service import PromptAssemblyService


def test_prompt_assembly_service_build_word_count_rule():
    rule = PromptAssemblyService.build_word_count_rule(2000, 4000, 3000)
    assert "2000 到 4000 字之间" in rule
    assert "目标约 3000 字" in rule


def test_prompt_assembly_service_extract_mission_patterns():
    version = SimpleNamespace(
        metadata_={
            "chapter_mission": {
                "opening_hook_type": "mystery_opening",
                "chapter_end_style": "knife_edge",
                "satisfaction_design": {"type": "twist_payoff"},
            }
        }
    )

    patterns = PromptAssemblyService.extract_mission_patterns(version)

    assert patterns["opening_hook_type"] == "mystery_opening"
    assert patterns["chapter_end_style"] == "knife_edge"
    assert patterns["satisfaction_type"] == "twist_payoff"


def test_prompt_assembly_service_build_prompt_sections_contains_core_sections():
    service = PromptAssemblyService(prompt_service=None, llm_service=None)
    sections = service.build_prompt_sections(
        writer_blueprint={"title": "书名"},
        previous_summary="上一章",
        previous_tail="上一章结尾",
        chapter_mission={"goal": "推进主线"},
        mission_brief_text="任务书",
        rag_context={"chunks": ["片段A"], "summaries": ["摘要A"]},
        knowledge_context="精筛知识",
        outline_title="第十章",
        outline_summary="大战将起",
        writing_notes="推进主线",
        forbidden_characters=["甲"],
        project_memory_text="长期记忆",
        memory_context="记忆层",
        platinum_writing_brief="白金规则",
        platinum_rhythm_brief="节奏规则",
        foreshadowing_urgency_brief="伏笔提醒",
        hook_continuity_brief="钩子提醒",
        emotion_expression_brief="情绪提醒",
        story_skeleton="故事骨架",
        genre_prompt_injection="题材约束",
        fingerprint_context="风格指纹",
        prediction_text="剧情推演",
        user_style_rules="用户风格",
        chapter_word_count_min=2000,
        chapter_word_count_max=4000,
        chapter_target_word_count=3000,
        chapter_state_context="角色状态",
        coolpoint_rhythm_directive="节奏纠偏",
        writing_strategy=SimpleNamespace(style_weight=1.0, reference_weight=1.0, genre_weight=1.0, warnings=[]),
        power_system_context="力量体系",
        relationship_context="角色关系",
        trajectory_context="轨迹分析",
    )

    titles = [title for title, _ in sections]
    assert "[当前章节目标]" in titles
    assert "[创作任务书](本章写作的核心执行指南，必须严格遵循)" in titles
    assert "[检索到的剧情上下文](Markdown)" in titles
    assert "[写作硬性约束](必须严格遵守)" in titles
