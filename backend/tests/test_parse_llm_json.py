"""json_utils.parse_llm_json 单测——统一健壮 LLM JSON 解析，替代脆弱切大括号。"""
import pytest

from app.utils.json_utils import parse_llm_json


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
