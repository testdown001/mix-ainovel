# -*- coding: utf-8 -*-
"""llm.log 正文预览脱敏（logging.llm_prompt_preview 三档）。

请求体里是用户创作全文，明文落盘属合规隐患；digest 档要既能对上 trace
（长度 + sha1 前 8 位）又不落全文，off 档完全不出正文，full 保留排障能力。
"""
import hashlib

from app.utils.llm_tool import (
    _normalize_preview_mode,
    format_body_preview,
)

SECRET = "这是一段不应完整落盘的用户创作内容。" * 20  # 远超 80 字符


def test_digest_contains_len_sha1_head_but_not_full_text():
    out = format_body_preview(SECRET, "digest")
    assert f"len={len(SECRET)}" in out
    expected_sha = hashlib.sha1(SECRET.encode("utf-8")).hexdigest()[:8]
    assert f"sha1={expected_sha}" in out
    assert SECRET[:80] in out
    # 第 81 字符起的内容绝不出现（head 之外的正文不落盘）
    assert SECRET[:81] not in out
    assert SECRET not in out


def test_off_hides_all_content_but_keeps_length():
    out = format_body_preview(SECRET, "off")
    assert SECRET[:10] not in out
    assert f"len={len(SECRET)}" in out


def test_full_keeps_text_up_to_limit():
    assert format_body_preview(SECRET, "full", full_limit=2000) == SECRET[:2000]
    assert format_body_preview("short", "full") == "short"


def test_full_limit_respected_for_response_previews():
    # 响应侧沿用原 200/500 字符上限，full 档不因换实现而膨胀日志
    assert format_body_preview(SECRET, "full", full_limit=200) == SECRET[:200]


def test_empty_text_yields_empty_preview():
    for mode in ("digest", "off", "full"):
        assert format_body_preview("", mode) == ""


def test_normalize_mode_defaults_to_digest():
    assert _normalize_preview_mode("full") == "full"
    assert _normalize_preview_mode("OFF") == "off"
    assert _normalize_preview_mode(" Digest ") == "digest"
    # 非法值/空值一律回默认 digest：宁可少记，不能因配置手误落全文
    assert _normalize_preview_mode("verbose") == "digest"
    assert _normalize_preview_mode("") == "digest"
    assert _normalize_preview_mode(None) == "digest"
