from types import SimpleNamespace
import asyncio
import pytest

from app.services.prompt_assembly_service import PromptAssemblyService
from app.services.prompt_budget_manager import PromptBudgetManager
from app.services.prompt_compiler_service import PromptCompilerService


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


def test_mission_brief_is_rendered_without_llm_call():
    class _NoLLM:
        async def get_llm_response(self, **kwargs):
            raise AssertionError("确定性任务书不应调用 LLM")

    service = PromptAssemblyService(prompt_service=None, llm_service=_NoLLM())
    brief = asyncio.run(
        service.generate_mission_brief(
            chapter_mission={
                "hard_constraints": {
                    "pov": "林玄",
                    "macro_beat": "P",
                    "macro_beat_description": "林玄被迫交出证物",
                    "chapter_end_style": "半句台词",
                    "forbidden": ["禁止全知词"],
                },
                "soft_suggestions": {"chapter_sellpoint": "证物当众反咬对手"},
                "scene_list": [{"location": "审讯室", "goal": "保住证物", "conflict": "上司施压"}],
            },
            previous_summary="上一章",
            previous_tail="上一章结尾",
            outline_title="交锋",
            outline_summary="林玄面对第一次正式审讯",
            writing_notes="不要解释背景",
            introduced_characters=["林玄"],
            forbidden_characters=["赵甲"],
            user_id=1,
        )
    )

    assert "证物当众反咬对手" in brief
    assert "林玄被迫交出证物" in brief
    assert "审讯室 → 保住证物 → 上司施压" in brief
    assert "禁止形容词和比喻连续堆叠" in brief
    assert "禁止未获准角色登场：赵甲" in brief


@pytest.mark.parametrize("container", [None, "hard_constraints", "soft_suggestions"])
def test_emotional_plan_survives_mission_brief_compilation_and_budget(container):
    intentions = {
        "chapter_type": "余波章",
        "emotion_curve": {
            "type": "悲伤",
            "curve": "强撑镇定到允许自己难过",
            "breathing_point": "整理遗物后独坐片刻",
        },
        "deliberate_omission": {"what": "不解释为何留下旧碗", "why": "让旧习惯承载失落"},
        "tone_guide": {"surface_texture": ["克制"], "ink_distribution": "详写收碗，略写回家路程"},
        "reader_promise": "读者想知道他会不会赴约",
    }
    intentions["scene_list"] = [{
        "location": "旧宅", "goal": "收拾饭桌", "turn": "留下空碗", "end_state": "决定赴约",
        "relationship_temp": "从回避师姐到默许她留下",
        "human_texture": ["碗沿有一道旧缺口"],
        "dialogue_noise": "师姐问话后等他自己回答",
        "transition_out": "以收碗的声音接到门外",
    }]
    mission = {container: intentions} if container else dict(intentions)
    brief = PromptAssemblyService.build_mission_brief(
        chapter_mission=mission, outline_title="旧碗", outline_summary="收拾遗物",
        writing_notes="", introduced_characters=[], forbidden_characters=[],
    )
    service = PromptAssemblyService(None, None)
    sections = service.build_prompt_sections(
        writer_blueprint={}, previous_summary="", previous_tail="", chapter_mission=mission,
        mission_brief_text=brief, rag_context=None, outline_title="旧碗", outline_summary="收拾遗物",
        writing_notes="", forbidden_characters=[], project_memory_text=None, memory_context=None,
        platinum_writing_brief=None, platinum_rhythm_brief=None, foreshadowing_urgency_brief=None,
        hook_continuity_brief=None, emotion_expression_brief=None,
    )
    # 与运行时同序：模块筛选 → 超预算裁剪 → cache 排序 → 正文 prompt。
    sections = [(title, "背景" * 20000 if title.startswith("[世界蓝图]") else content)
                for title, content in sections]
    compiled, _ = PromptCompilerService().compile(
        plan=SimpleNamespace(prompt_modules=["mission_brief", "world_blueprint"], skill_policies=[]),
        sections=sections,
    )
    manager = PromptBudgetManager()
    budgeted = manager.reorder_for_cache(manager.apply_budget(compiled))
    final_prompt = "\n\n".join(content for _, content in budgeted)
    assert len(final_prompt) < 10000  # 确实经过了裁剪，而非只在原始 JSON 中找到标记。
    assert not any(title.startswith("[章节导演脚本]") for title, _ in budgeted)
    for intent in (
        "余波章", "强撑镇定到允许自己难过", "整理遗物后独坐片刻",
        "不解释为何留下旧碗", "让旧习惯承载失落", "详写收碗，略写回家路程",
        "读者想知道他会不会赴约", "从回避师姐到默许她留下", "碗沿有一道旧缺口",
        "师姐问话后等他自己回答", "以收碗的声音接到门外",
    ):
        assert intent in final_prompt


def test_sparse_mission_does_not_invent_emotional_plan():
    brief = PromptAssemblyService.build_mission_brief(
        chapter_mission={"soft_suggestions": {"emotion_curve": None, "deliberate_omission": {}}},
        outline_title="行路", outline_summary="进城", writing_notes="",
        introduced_characters=[], forbidden_characters=[],
    )
    assert "【情感与留白执行】" not in brief
    assert "None" not in brief
