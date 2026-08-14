"""风格样本清洗回归：LLM 任务复述不得入库（2026-08-14 线上实发）。

搜索通道模型偶尔把任务要求复述一遍当作输出（「分析请求：角色：小说风格分析师。
任务：模仿……」），此前原样存进 style_samples_content，档案页展示垃圾并被
format_style_samples_for_prompt 注入正文生成。
"""
from app.services.reference_novel_library_service import ReferenceNovelLibraryService

clean = ReferenceNovelLibraryService._clean_style_samples

ECHO_OUTPUT = """1. **分析请求**:
    * 角色：小说风格分析师。
    * 任务：模仿《神秘复苏》的语言节奏，输出 10 段短文风格样本。
    * 输入：提供了《神秘复苏》的写法分析（第三人称限制视角等）。
"""

CLEAN_SAMPLES = """楼道里的声控灯灭了。杨间没有动，数着自己的心跳，一下，两下。

---

那口井就在院子正中央。白天路过八次，他没觉得有什么，现在它像一只睁开的眼睛。

---

“别回头。”老孙的声音压得极低，“它就贴着你后脖颈。”"""


def test_echo_only_output_cleared():
    assert clean(ECHO_OUTPUT) == ""


def test_clean_samples_preserved():
    result = clean(CLEAN_SAMPLES)
    assert "声控灯灭了" in result
    assert "别回头" in result
    assert result.count("---") == 2


def test_mixed_preamble_dropped_samples_kept():
    mixed = "以下是模仿《神秘复苏》的 10 段风格样本：\n\n" + CLEAN_SAMPLES
    result = clean(mixed)
    assert "以下是" not in result
    assert "声控灯灭了" in result


def test_markdown_headers_dropped():
    text = "### 剧情节奏说明\n\n" + "夜里的风把纸人吹得转了半圈，它的脸正对着窗户。"
    result = clean(text)
    assert "###" not in result
    assert "纸人" in result


def test_empty_and_blank():
    assert clean("") == ""
    assert clean("   \n  ") == ""


# ── 2026-08-14 线上第二变体：分析笔记/写作计划（非任务复述但同样是垃圾） ──

ANALYSIS_NOTES = """2. 解构《大奉打更人》风格：
    * 句式：短句为主，短段落。动作+对话驱动。
    * 节奏：快，信息密度低，推进快。

3. 构建10段样本（结合剧情元素，不提现实信息）：
    段1：开局破案/内心吐槽，许七安着卷宗。
    段2：打更人衙门日常/对话，与同僚插科打诨。"""


def test_analysis_notes_variant_cleared():
    assert clean(ANALYSIS_NOTES) == ""


def test_numbered_segment_dropped():
    mixed = "1. 先看叙事视角与节奏\n\n" + "更声过了三巡，他把灯笼压低，影子贴着墙根走。"
    result = clean(mixed)
    assert "叙事视角" not in result
    assert "灯笼" in result


def test_bullet_structure_dropped_single_bullet_kept():
    # ≥2 行 bullet 是分析笔记；正文里偶然一行破折号式开头不误伤
    notes = "* 句式：短句\n* 节奏：快"
    assert clean(notes) == ""
    prose = "夜风扫过长街。\n- 更声，三下。\n他数完才敢迈步。"
    assert clean(prose) != ""


def test_outline_task_echo_detection():
    echo_head = ReferenceNovelLibraryService._looks_like_task_echo
    assert echo_head("1.  **理解任务需求**：\n    *   角色：经验丰富的小说策划编辑。")
    assert echo_head("分析请求：抽取《某书》核心大纲")
    assert not echo_head("### 剧情大纲\n\n1. **第一阶段：税银案**\n许七安卷入税银失窃案……")
