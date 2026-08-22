"""章节克制叙事、有限视角和自然收尾的回归测试。"""

from pathlib import Path

from app.core.constants import ALL_HARD_RULES
from app.services.chapter_guardrails import ChapterGuardrails
from app.services.generation_policy_service import GenerationPolicyService
from app.services.humanization_service import HumanizationService
from app.services.prompt_assembly_service import PromptAssemblyService


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def _humanization_service() -> HumanizationService:
    service = HumanizationService.__new__(HumanizationService)
    service.session = None
    service.llm_service = None
    service.prompt_service = None
    return service


def test_hard_rules_balance_emotion_pov_and_ending():
    assert "简单情绪允许直陈" in ALL_HARD_RULES
    assert "同一情绪节拍最多保留一个身体反应" in ALL_HARD_RULES
    assert "严格使用当前 POV 的有限视角" in ALL_HARD_RULES
    assert "最后两段禁止命运、风暴、光影" in ALL_HARD_RULES
    assert "每段对话必须附带" not in ALL_HARD_RULES
    assert "每章至少出现2次" not in ALL_HARD_RULES


def test_emotion_brief_does_not_force_body_or_environment_metaphors():
    brief = PromptAssemblyService.build_emotion_expression_brief([])
    assert "简单情绪允许用一句朴素判断直说" in brief
    assert "最多保留一个身体反应" in brief
    assert "不要用天气、光影、空气或温度替人物抒情" in brief


def test_version_hints_no_longer_reward_sensory_stacking_or_forced_endings():
    hints = GenerationPolicyService.resolve_style_hints(None, 3)
    assert all("多写内心戏和感官描写" not in hint for hint in hints)
    assert all("结尾钩子更强" not in hint for hint in hints)
    assert "不堆身体反应和修饰语" in hints[0]
    assert "不强行升华或使用象征隐喻" in hints[2]


def test_current_pov_inner_judgment_is_not_treated_as_ai_vocabulary():
    report = _humanization_service().scan("他知道门外有人，便把灯关了。她害怕，却还是握住门把手。")
    lexical_descriptions = [issue.description for issue in report.issues if issue.category == "ai_vocabulary"]
    assert not any("他知道" in description for description in lexical_descriptions)
    assert not any("她害怕" in description for description in lexical_descriptions)


def test_humanization_scan_flags_figurative_and_body_reaction_stacking():
    paragraph = (
        "他的心跳像擂鼓，掌心沁出冷汗，喉结滚动，指尖发白，胸口发紧，"
        "目光一凝，仿佛黑暗正在逼近，似乎空气也在等待。"
    )
    report = _humanization_service().scan("\n".join([paragraph] * 12))
    categories = {issue.category for issue in report.issues}
    assert "figurative_density" in categories
    assert "body_reaction_stack" in categories


def test_guardrail_enforces_explicit_pov_even_for_loose_genre():
    result = ChapterGuardrails().check(
        generated_text="林舟关上门。无人知道，楼上的人已经拔出刀。",
        forbidden_characters=[],
        pov="林舟",
        omniscient_tolerance="loose",
    )
    assert any(item.type == "omniscient_cue" for item in result.violations)


def test_guardrail_removes_omniscient_sentence_not_only_transition_word():
    guardrails = ChapterGuardrails()
    text = "林舟关上门。与此同时，楼上的人已经拔出刀。林舟走向楼梯。"
    result = guardrails.check(text, forbidden_characters=[], pov="林舟")
    patched = guardrails.apply_local_patches(text, result)
    assert "与此同时" not in patched
    assert "楼上的人已经拔出刀" not in patched
    assert "林舟走向楼梯" in patched


def test_guardrail_trims_metaphorical_final_sentence_and_keeps_concrete_landing():
    guardrails = ChapterGuardrails()
    text = "林舟把证物袋锁进柜子。\n\n走廊尽头的灯光闪了闪，仿佛在为更大的风暴预告。"
    result = guardrails.check(text, forbidden_characters=[], pov="林舟")
    assert any(item.type == "ai_metaphor_ending" for item in result.violations)
    patched = guardrails.apply_local_patches(text, result)
    assert patched == "林舟把证物袋锁进柜子。"


def test_guardrail_keeps_concrete_action_in_dark_environment():
    result = ChapterGuardrails().check(
        generated_text="林舟关掉手电。在黑暗中，他正在撬开那扇铁门。",
        forbidden_characters=[],
        pov="林舟",
    )
    assert not any(item.type == "ai_metaphor_ending" for item in result.violations)


def test_all_writer_prompts_contain_prose_discipline_rules():
    for filename in ("writing.md", "writing_v2.md", "writing_v3.md", "writing_fast.md"):
        content = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
        assert "有限" in content and "POV" in content, filename
        assert "身体反应" in content, filename
        assert "最后两段" in content, filename


def test_repair_prompts_do_not_reintroduce_physiological_stacking():
    editor = (PROMPTS_DIR / "editor_review.md").read_text(encoding="utf-8")
    density = (PROMPTS_DIR / "density_compression.md").read_text(encoding="utf-8")
    rewrite = (PROMPTS_DIR / "rewrite_guardrails.md").read_text(encoding="utf-8")
    assert "必须通过生理反应" not in editor
    assert "必须增加至少 3 个" not in density
    assert "仿佛有什么危险正在逼近" not in rewrite
