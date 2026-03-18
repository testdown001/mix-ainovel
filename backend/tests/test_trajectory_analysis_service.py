import asyncio
from types import SimpleNamespace

from app.services.trajectory_analysis_service import TrajectoryAnalysisService


def test_trajectory_analysis_service_prefetch_uses_cached_guidance(monkeypatch):
    from app.services import trajectory_analysis_service as module

    cache_service = SimpleNamespace(
        get=lambda key: asyncio.sleep(0, result={
            "overall_assessment": "节奏稳定",
            "weaknesses": ["爆点不足"],
            "next_chapter_suggestions": ["提高冲突强度"],
        })
    )
    monkeypatch.setattr(module, "get_cache_service", lambda: cache_service)

    service = TrajectoryAnalysisService()
    text = asyncio.run(
        service.prefetch_trajectory_context(
            project_id="proj-1",
            project=SimpleNamespace(chapters=[]),
            chapter_number=6,
        )
    )

    assert "总体评估: 节奏稳定" in text
    assert "提高冲突强度" in text


def test_trajectory_analysis_service_skips_with_insufficient_points(monkeypatch):
    from app.services import trajectory_analysis_service as module

    cache_service = SimpleNamespace(get=lambda key: asyncio.sleep(0, result=None))
    monkeypatch.setattr(module, "get_cache_service", lambda: cache_service)

    service = TrajectoryAnalysisService()
    project = SimpleNamespace(
        chapters=[
            SimpleNamespace(chapter_number=1, selected_version=SimpleNamespace(metadata_={})),
            SimpleNamespace(chapter_number=2, selected_version=None),
        ]
    )

    text = asyncio.run(
        service.prefetch_trajectory_context(
            project_id="proj-2",
            project=project,
            chapter_number=4,
        )
    )

    assert text is None
