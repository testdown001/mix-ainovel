"""模型自称过滤（strip_model_self_identification）回归：

匿名模型策略（章鱼分档）的出口防线——正文中出现厂商/模型品牌自称必须被剔除，
但普通叙事（含科幻角色自称"人工智能"的合法台词）不能误伤。
"""
from app.utils.json_utils import (
    sanitize_chapter_plain_text,
    strip_model_self_identification,
)

# 一段足够长的正常叙事，保证长度阈值与 20% 占比守卫不受干扰
_NARRATIVE = (
    "夜色沉了下来，长街尽头的灯笼一盏盏亮起。"
    "沈青梧握紧了手中的剑，指节因用力而泛白。"
    "她知道，今晚过后，云京城再无她的容身之处。"
    "远处传来更鼓声，一声，又一声，像是敲在人心上。"
    "巷口的老槐树下，卖馄饨的摊子还冒着热气，摊主压低了斗笠，仿佛什么都没有看见。"
    "沈青梧深吸一口气，把剑收回鞘中，转身走进了浓得化不开的夜色里。"
    "她的脚步很轻，轻得像一片落叶，可每一步都踩在命运的刀刃上。"
    "城楼上的守卫换了岗，谁也没有注意到，一道影子已经越过了三丈高的宫墙。"
)


def test_strips_chinese_brand_self_identification():
    leaked = _NARRATIVE + "我是Claude，一个由Anthropic开发的AI助手。" + _NARRATIVE
    cleaned = strip_model_self_identification(leaked)
    assert "Claude" not in cleaned
    assert "Anthropic" not in cleaned
    assert "沈青梧" in cleaned  # 正常叙事保留


def test_strips_english_self_identification():
    leaked = _NARRATIVE + "\nAs an AI language model, I cannot continue this story.\n" + _NARRATIVE
    cleaned = strip_model_self_identification(leaked)
    assert "As an AI language model" not in cleaned
    assert "长街尽头" in cleaned


def test_keeps_generic_ai_character_dialogue():
    # 科幻角色自称"人工智能"是合法叙事，不含品牌词 → 必须原样保留
    text = _NARRATIVE + "舱内响起冰冷的声音：「我是人工智能，编号七七三。」" + _NARRATIVE
    assert strip_model_self_identification(text) == text


def test_keeps_text_without_any_brand():
    assert strip_model_self_identification(_NARRATIVE) == _NARRATIVE
    assert strip_model_self_identification("") == ""


def test_overscrub_guard_keeps_original():
    # 命中句占比过高（如整段都在谈这些品牌）→ 疑似误判，保留原文
    text = "Claude发布了新版本。DeepSeek紧随其后。Kimi也不甘示弱。"
    assert strip_model_self_identification(text) == text


def test_kimi_word_boundary_no_false_positive():
    # "Kimiko"（人名）不应触发 Kimi 品牌匹配
    text = _NARRATIVE + "Kimiko turned around and smiled." + _NARRATIVE
    assert strip_model_self_identification(text) == text


def test_sanitize_chapter_plain_text_integrates_filter():
    raw = "好的，以下是第三章：\n\n" + _NARRATIVE + "\n我是ChatGPT，很高兴为您写作。\n" + _NARRATIVE
    cleaned = sanitize_chapter_plain_text(raw)
    assert "ChatGPT" not in cleaned
    assert "沈青梧" in cleaned
    assert not cleaned.startswith("好的")
