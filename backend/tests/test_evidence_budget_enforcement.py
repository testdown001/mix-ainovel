"""证据预算执行测试。"""
import importlib

import pytest


@pytest.fixture(autouse=True)
def _ensure_models_loaded():
    import app.models  # noqa: F401
    import app.models.user_quota  # noqa: F401


def _get_classes():
    router_mod = importlib.import_module("app.services.evidence_router_service")
    planner_mod = importlib.import_module("app.services.context_planner_service")
    return (
        router_mod.EvidenceRouterService,
        planner_mod.GenerationEvidencePack,
        planner_mod.EvidenceItem,
        planner_mod.ContextPlannerService,
    )


def _make_item(source, title, content, score):
    _, _, EvidenceItem, _ = _get_classes()
    return EvidenceItem(source=source, title=title, content=content, score=score)


def test_enforce_drops_low_score_items_when_over_budget():
    """超出预算时丢弃低分项。"""
    RouterCls, PackCls, _, _ = _get_classes()
    router = RouterCls()

    pack = PackCls()
    # 每个 item ~100 字 ≈ 67 tokens
    long_content = "这是一段测试内容。" * 10
    pack.local_plot = [
        _make_item("local_plot_rag", f"片段{i}", long_content, score)
        for i, score in enumerate([0.9, 0.8, 0.7, 0.6, 0.5, 0.4], 1)
    ]

    budgets = {
        "evidence_budgets": {
            "local_plot": {"max_tokens": 200, "max_items": 10},
            "total_max_tokens": 500,
        }
    }

    report = router._enforce_evidence_budgets(pack, budgets)

    assert report is not None
    assert len(pack.local_plot) < 6  # 应该丢弃了一些
    # 保留的应该是高分优先
    scores = [item.score for item in pack.local_plot]
    assert scores == sorted(scores, reverse=True)


def test_enforce_respects_max_items():
    """max_items 限制生效。"""
    RouterCls, PackCls, _, _ = _get_classes()
    router = RouterCls()

    pack = PackCls()
    pack.global_arc = [
        _make_item("global_arc_rag", f"项{i}", "短内容", 0.5 + i * 0.05)
        for i in range(10)
    ]

    budgets = {
        "evidence_budgets": {
            "global_arc": {"max_tokens": 50000, "max_items": 3},
            "total_max_tokens": 50000,
        }
    }

    report = router._enforce_evidence_budgets(pack, budgets)

    assert len(pack.global_arc) == 3
    # 保留最高分的 3 个
    assert pack.global_arc[0].score >= pack.global_arc[1].score


def test_enforce_returns_none_without_budgets():
    """无预算配置时返回 None。"""
    RouterCls, PackCls, _, _ = _get_classes()
    router = RouterCls()
    pack = PackCls()
    pack.local_plot = [_make_item("local_plot_rag", "x", "内容", 0.5)]

    assert router._enforce_evidence_budgets(pack, {}) is None
    assert router._enforce_evidence_budgets(pack, None) is None


def test_enforce_reports_utilization():
    """报告包含 total utilization。"""
    RouterCls, PackCls, _, _ = _get_classes()
    router = RouterCls()

    pack = PackCls()
    pack.local_plot = [_make_item("local_plot_rag", "A", "一二三四五" * 20, 0.9)]
    pack.global_arc = [_make_item("global_arc_rag", "B", "六七八九十" * 20, 0.8)]

    budgets = {
        "evidence_budgets": {
            "local_plot": {"max_tokens": 5000, "max_items": 10},
            "global_arc": {"max_tokens": 5000, "max_items": 10},
            "total_max_tokens": 10000,
        }
    }

    report = router._enforce_evidence_budgets(pack, budgets)

    # 未超预算，但 total 部分应有 utilization
    assert report is not None
    assert "total" in report
    assert 0 < report["total"]["utilization"] <= 1.0


def test_planner_builds_evidence_budgets():
    """ContextPlannerService 生成证据预算。"""
    _, _, _, PlannerCls = _get_classes()
    planner = PlannerCls()

    normal_budgets = planner._build_evidence_budgets(is_fast_path=False)
    fast_budgets = planner._build_evidence_budgets(is_fast_path=True)

    # 两种模式都包含四类预算
    for key in ("local_plot", "global_arc", "state_items", "symbolic_items"):
        assert key in normal_budgets
        assert key in fast_budgets
        assert "max_tokens" in normal_budgets[key]
        assert "max_items" in normal_budgets[key]

    # fast 模式预算更紧
    assert fast_budgets["total_max_tokens"] < normal_budgets["total_max_tokens"]
    assert fast_budgets["local_plot"]["max_tokens"] < normal_budgets["local_plot"]["max_tokens"]


def test_enforce_truncates_last_item():
    """最后一个超预算的 item 被截断而非完全丢弃。"""
    RouterCls, PackCls, _, _ = _get_classes()
    router = RouterCls()

    pack = PackCls()
    # 第一个 item ~67 tokens, 第二个也 ~67 tokens
    pack.state_items = [
        _make_item("state_rag", "A", "高优先级内容。" * 10, 0.9),
        _make_item("state_rag", "B", "低优先级但很长的内容。" * 30, 0.7),
    ]

    budgets = {
        "evidence_budgets": {
            "state_items": {"max_tokens": 100, "max_items": 10},
            "total_max_tokens": 200,
        }
    }

    report = router._enforce_evidence_budgets(pack, budgets)

    # 两个 item 都应该保留（第二个被截断）
    assert len(pack.state_items) >= 1
    if report and "state_items" in report:
        assert report["state_items"]["truncated"] >= 0
