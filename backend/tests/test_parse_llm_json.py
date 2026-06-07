"""json_utils.parse_llm_json 单测——统一健壮 LLM JSON 解析，替代脆弱切大括号。"""
import pytest

from app.utils.json_utils import is_probable_chapter_plain_text, parse_llm_json, sanitize_chapter_plain_text


def test_plain_object():
    assert parse_llm_json('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_array_top_level():
    # 数组顶层（旧 find('{')..rfind('}') 会解析错误）
    assert parse_llm_json("[1, 2, 3]") == [1, 2, 3]


def test_markdown_fenced():
    assert parse_llm_json('```json\n{"k": [1,2]}\n```') == {"k": [1, 2]}


def test_object_with_surrounding_text():
    assert parse_llm_json('这是结果：{"ok": true} 以上') == {"ok": True}


def test_think_tags_stripped():
    raw = '<think>让我想想</think>{"v": 42}'
    assert parse_llm_json(raw) == {"v": 42}


def test_invalid_returns_default():
    assert parse_llm_json("完全不是JSON", default=None) is None
    assert parse_llm_json("", default={"fallback": 1}) == {"fallback": 1}


def test_invalid_without_default_raises():
    with pytest.raises(ValueError):
        parse_llm_json("根本不是json也修不好的~~~")


def test_none_input_with_default():
    assert parse_llm_json(None, default=[]) == []


def test_sanitize_chapter_plain_text_strips_editor_task_analysis_prefix():
    raw = """1.  分析任务要求：
角色：文学功底深厚的网文润色编辑。
目标：提升文学性、画面感、沉浸感，强化感官描写（视听触等）。
限制：保持情节、人物关系、对话内容完全不变；字数不超过4000字；不增删情节；直接输出润色后内容，无其他废话。

润色后内容：
雨声砸在青瓦上，沈砚推开窗，冷风卷着潮气扑进屋内。
"""

    assert sanitize_chapter_plain_text(raw) == "雨声砸在青瓦上，沈砚推开窗，冷风卷着潮气扑进屋内。"


def test_sanitize_chapter_plain_text_returns_empty_for_meta_only_editor_output():
    raw = """1.  分析任务要求：
角色：文学功底深厚的网文润色编辑。
目标：提升文学性、画面感、沉浸感，强化感官描写（视听触等）。
限制：保持情节、人物关系、对话内容完全不变；字数不超过4000字；不增删情节；直接输出润色后内容，无其他废话。
"""

    assert sanitize_chapter_plain_text(raw) == ""


def test_sanitize_chapter_plain_text_strips_version_content_meta_only_output():
    raw = """版本内容为：1.  分析任务要求：
角色：文学功底深厚的网文润色编辑。
目标：提升文学性、画面感、沉浸感，强化感官描写（视听触等）。
限制：保持情节、人物关系、对话内容完全不变；字数不超过4000字；不增删情节；直接输出润色后内容，无其他废话。
"""

    assert sanitize_chapter_plain_text(raw) == ""


def test_sanitize_chapter_plain_text_strips_editor_analysis_and_original_text_analysis():
    raw = """1.  分析任务：
角色：擅长小说润色的文学编辑。
目标：在保持原有情节、人物关系、对话内容完全不变的前提下，提升文字的文学性和画面感。
限制：总字数不超过4000字，不增删情节，直接输出润色后的完整章节，不输出其他内容。

2.  原文本分析：
情节：直播恋综中，唐亦薇和林摆观点碰撞。
人物：
林摆：男主，看似摆烂实则被压迫。
唐亦薇：前妻，精英做派，控制狂。
氛围：从综艺的荒诞搞笑，到儿子出场后的窒息、心酸。
需要提升的地方：
画面感：场景细节可以更细腻。
感官描写：声音、触觉、视觉。
文学性：遣词造句更凝练。
"""

    assert sanitize_chapter_plain_text(raw) == ""


def test_sanitize_chapter_plain_text_keeps_inline_version_content_body():
    raw = "版本内容为：雨声砸在青瓦上，沈砚推开窗。"

    assert sanitize_chapter_plain_text(raw) == "雨声砸在青瓦上，沈砚推开窗。"


def test_is_probable_chapter_plain_text_rejects_prompt_analysis_output():
    raw = """1.  分析任务：
角色：擅长小说润色的文学编辑。
目标：在保持原有情节、人物关系、对话内容完全不变的前提下，提升文字的文学性和画面感。
限制：总字数不超过4000字，不增删情节，直接输出润色后的完整章节，不输出其他内容。

2.  原文本分析：
情节：直播恋综中，唐亦薇和林摆观点碰撞。
人物：
林摆：男主，看似摆烂实则被压迫。
唐亦薇：前妻，精英做派，控制狂。
氛围：从综艺的荒诞搞笑，到儿子出场后的窒息、心酸。
"""

    assert is_probable_chapter_plain_text(raw) is False


def test_is_probable_chapter_plain_text_accepts_long_narrative_body():
    body = (
        "雨声砸在青瓦上，沈砚推开窗，冷风卷着潮气扑进屋内。"
        "街口的灯笼被风吹得一晃一晃，红光落在他的指节上，像一层迟迟不肯退去的血色。"
        "他听见楼下有人压低声音争吵，茶盏碰在桌沿，发出短促的一声响。"
        "那声音让他想起昨夜未写完的信，也想起信尾被墨水洇开的名字。"
    )

    assert is_probable_chapter_plain_text(body) is True
