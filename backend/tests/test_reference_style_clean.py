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
