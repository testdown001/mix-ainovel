"""灵感扰动池（concept 对话发散注入）单测。"""
import random

from app.services.inspiration_spark import (
    SPARK_CARDS,
    SparkCard,
    pick_spark,
    build_spark_injection,
)


def test_pool_nonempty_and_well_formed():
    assert len(SPARK_CARDS) >= 10
    for c in SPARK_CARDS:
        assert isinstance(c, SparkCard)
        assert c.category and c.prompt


def test_pick_spark_returns_card_from_pool():
    card = pick_spark()
    assert card in SPARK_CARDS


def test_pick_spark_deterministic_with_seed():
    a = pick_spark(random.Random(42))
    b = pick_spark(random.Random(42))
    assert a == b  # 相同种子可复现（便于测试/排障）


def test_build_injection_contains_card_and_guardrails():
    card = SparkCard("反转", "把开局反过来")
    text = build_spark_injection(card)
    assert "反转" in text
    assert "把开局反过来" in text
    # 必须含"仅你可见/不要复述"类护栏，避免把灵感卡当元话术讲给用户
    assert "切勿直接复述" in text or "仅你可见" in text
    assert "为了用而用" in text


def test_spark_variety_categories():
    cats = {c.category for c in SPARK_CARDS}
    # 覆盖多种发散维度，避免同质
    assert len(cats) >= 6
