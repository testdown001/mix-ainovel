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


def _chapter(num: int, *, mission=None):
    metadata = {"chapter_mission": mission} if mission is not None else {}
    return SimpleNamespace(
        chapter_number=num,
        selected_version=SimpleNamespace(metadata_=metadata),
    )


def test_build_emotion_points_prefers_actual_character_state_intensity():
    """核心修复：CharacterState 实际峰值优先于恒定 5.0，故事曲线不再被压平。"""
    project = SimpleNamespace(chapters=[_chapter(1), _chapter(2), _chapter(3)])
    points = TrajectoryAnalysisService._build_emotion_points(
        project=project,
        chapter_number=5,
        actual_intensity={1: 3.0, 2: 7.0, 3: 9.0},
    )
    assert [p["intensity"] for p in points] == [3.0, 7.0, 9.0]
    assert [p["primary_intensity"] for p in points] == [3.0, 7.0, 9.0]


def test_build_emotion_points_fallback_chain():
    """实际强度缺 → 退 mission 规划强度（当前从无写入）；皆缺 → 默认 5.0。"""
    project = SimpleNamespace(
        chapters=[
            _chapter(1, mission={"satisfaction_design": {"intensity": 8}}),
            _chapter(2),
            _chapter(3),
        ]
    )
    points = TrajectoryAnalysisService._build_emotion_points(
        project=project,
        chapter_number=5,
        actual_intensity={2: 6.0},
    )
    by_ch = {p["chapter_number"]: p["intensity"] for p in points}
    assert by_ch[1] == 8.0  # 实际无该章 → 退回 mission 规划强度
    assert by_ch[2] == 6.0  # 实际有 → 优先实际，覆盖空 mission
    assert by_ch[3] == 5.0  # 两者皆无 → 默认


def test_actual_intensity_map_parses_and_skips_dirty_rows(monkeypatch):
    from app.services import emotion_deviation_service as eds

    async def _curve(self, project_id, before_chapter, *, session=None):
        return [
            {"chapter_number": 1, "intensity": 3.0},
            {"chapter_number": "2", "intensity": "7"},  # 可转换 → 收录
            {"chapter_number": None, "intensity": 9},   # 章号缺失 → 跳过
            {"chapter_number": 3, "intensity": None},   # 强度缺失 → 跳过
        ]

    monkeypatch.setattr(eds.EmotionDeviationService, "build_actual_intensity_curve", _curve)
    result = asyncio.run(
        TrajectoryAnalysisService._actual_intensity_map(project_id="p", before_chapter=5)
    )
    assert result == {1: 3.0, 2: 7.0}


def test_actual_intensity_map_degrades_on_error(monkeypatch):
    from app.services import emotion_deviation_service as eds

    async def _boom(self, *args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(eds.EmotionDeviationService, "build_actual_intensity_curve", _boom)
    result = asyncio.run(
        TrajectoryAnalysisService._actual_intensity_map(project_id="p", before_chapter=5)
    )
    assert result == {}


def test_prefetch_actual_intensity_yields_non_flat_curve(monkeypatch):
    """端到端：cache miss + 实际情绪曲线 → 波动性 > 0（修复前恒 5.0 → 0.00/FLAT）。"""
    from app.services import trajectory_analysis_service as module

    cache_service = SimpleNamespace(get=lambda key: asyncio.sleep(0, result=None))
    monkeypatch.setattr(module, "get_cache_service", lambda: cache_service)
    monkeypatch.setattr(
        module.TrajectoryAnalysisService,
        "_actual_intensity_map",
        staticmethod(
            lambda **kwargs: asyncio.sleep(0, result={1: 2.0, 2: 5.0, 3: 8.0, 4: 4.0})
        ),
    )

    service = TrajectoryAnalysisService()

    async def _no_deviation(**kwargs):
        return None

    service._build_deviation_brief = _no_deviation

    project = SimpleNamespace(chapters=[_chapter(n) for n in range(1, 6)])
    text = asyncio.run(
        service.prefetch_trajectory_context(
            project_id="proj-3", project=project, chapter_number=6
        )
    )

    assert text is not None
    assert "波动性:" in text
    assert "波动性: 0.00" not in text  # 不再是被压平的曲线
