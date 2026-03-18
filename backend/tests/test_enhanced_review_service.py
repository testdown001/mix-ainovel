import asyncio
from types import SimpleNamespace

from app.services.enhanced_review_service import EnhancedReviewService


def test_enhanced_review_service_collects_critical_issues():
    service = EnhancedReviewService(
        db=SimpleNamespace(),
        llm_service=SimpleNamespace(),
        prompt_service=SimpleNamespace(),
    )
    service.review_service = SimpleNamespace(
        review_chapter=lambda **kwargs: asyncio.sleep(0, result={
            "critical_issues_count": 1,
            "priority_fixes": ["补强主角动机"],
        })
    )
    service.constitution_service = SimpleNamespace(
        check_compliance=lambda **kwargs: asyncio.sleep(0, result={
            "overall_compliance": False,
            "violations": [{"severity": "critical", "description": "世界观硬约束冲突"}],
        })
    )
    service.writer_persona_service = SimpleNamespace(
        check_style_compliance=lambda **kwargs: asyncio.sleep(0, result={"score": 82})
    )

    result = asyncio.run(
        service.post_generation_review(
            project_id="proj-1",
            chapter_number=12,
            chapter_title="测试章",
            chapter_content="正文",
        )
    )

    assert result["overall_passed"] is False
    assert "补强主角动机" in result["critical_issues"]
    assert "世界观硬约束冲突" in result["critical_issues"]
    assert result["style_compliance"]["score"] == 82
