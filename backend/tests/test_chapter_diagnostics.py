from app.utils.chapter_diagnostics import (
    analyze_chapter_text,
    extract_retrieval_metrics,
    extract_review_issues,
    extract_review_scores,
)


def test_extract_retrieval_metrics_handles_list_and_count_payloads():
    metrics_from_lists = extract_retrieval_metrics(
        {
            "chunks": ["片段1", "", "片段3"],
            "summaries": ["摘要1"],
        }
    )
    assert metrics_from_lists == {
        "chunks": 3,
        "summaries": 1,
        "hit_rate": 0.75,
    }

    metrics_from_counts = extract_retrieval_metrics(
        {
            "chunks": 2,
            "summaries": 1,
        }
    )
    assert metrics_from_counts == {
        "chunks": 2,
        "summaries": 1,
        "hit_rate": 1.0,
    }


def test_extract_review_scores_and_issues_from_nested_review_payload():
    payload = {
        "quality_detection": {
            "overall_score": 82,
            "details": {"score": 78},
        },
        "reader_simulator": {"status": "scheduled_async"},
        "humanization": {"error": "timeout"},
    }

    scores = extract_review_scores(payload)
    issues = extract_review_issues(payload)

    assert ("quality detection", 82.0) in scores
    assert ("details", 78.0) in scores
    assert any(issue["type"] == "reader simulator分析" for issue in issues)
    assert any(issue["type"] == "humanization分析" for issue in issues)


def test_analyze_chapter_text_reports_short_content_placeholders_and_think_tags():
    content = """<think>草稿</think>

TODO：这里待补。

“你来了？”他问。
“嗯。”她点头。
"""

    result = analyze_chapter_text(content)

    issue_types = {issue["type"] for issue in result["issues"]}
    assert result["metrics"]["word_count"] > 0
    assert "章节字数" in issue_types
    assert "输出清洗" in issue_types
    assert "占位符残留" in issue_types
    assert result["suggestions"]


def test_diagnostic_product_summary_shape_is_stable():
    summary = {
        "verdict": "本章可用但建议小修，优先处理下方风险点",
        "primary_risk": "章节评审均分 72 分，有提升空间",
        "next_action": "确认满意版本后定稿，并继续推进下一章",
        "confidence": "high",
    }

    assert set(summary) == {"verdict", "primary_risk", "next_action", "confidence"}
    assert summary["confidence"] in {"high", "medium", "low"}
