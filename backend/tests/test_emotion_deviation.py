"""情感曲线偏差比对 (A5)：EmotionDeviationService。

覆盖：
- compute_deviation_brief 纯比对：低于规划 / 高于规划 / 贴合规划(None) / 数据不足(None)；
- _aggregate_intensity_by_chapter 取本章情绪峰值 + 脏数据容错；
- build_actual_intensity_curve 从 CharacterState 读取并按章聚合(注入内存会话)；
- build_brief 端到端：有实际快照→产出提示；无快照→降级 None。
不触网、不触 LLM。
"""
import asyncio
from types import SimpleNamespace

import app.models  # noqa: F401  mapper 注册
from app.db.base import Base
from app.models.memory_layer import CharacterState
from app.services.emotion_deviation_service import EmotionDeviationService

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


def _make_sessionmaker():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


def _expected(intensities, phase="rising_action"):
    """构造规划曲线：第 i 章强度 intensities[i-1]。"""
    return [
        {"chapter_number": i + 1, "emotion_intensity": v, "narrative_phase": phase}
        for i, v in enumerate(intensities)
    ]


def _actual(pairs):
    """构造实际曲线：[(chapter_number, intensity), ...]。"""
    return [{"chapter_number": ch, "intensity": v, "emotion": ""} for ch, v in pairs]


# ----------------------------------------------------------------- 纯比对逻辑
def test_compute_deviation_brief_flags_below_plan():
    svc = EmotionDeviationService()
    expected = _expected([5, 5, 6, 7, 8, 9, 9], phase="climax")
    actual = _actual([(3, 4), (4, 4), (5, 4), (6, 4)])  # 实际明显低于规划
    brief = svc.compute_deviation_brief(expected, actual, next_chapter=7)
    assert brief is not None
    assert "低于规划" in brief
    assert "本章规划强度" in brief and "9.0" in brief  # 第7章规划强度=9
    assert "情感曲线偏差校正" in brief


def test_compute_deviation_brief_flags_above_plan():
    svc = EmotionDeviationService()
    expected = _expected([3, 3, 3, 3, 3, 3, 3])
    actual = _actual([(3, 9), (4, 9), (5, 9), (6, 9)])  # 实际持续高于规划
    brief = svc.compute_deviation_brief(expected, actual, next_chapter=7)
    assert brief is not None
    assert "高于规划" in brief
    assert "缓冲" in brief


def test_compute_deviation_brief_on_track_returns_none():
    svc = EmotionDeviationService()
    expected = _expected([5, 5, 5, 5, 5, 5, 5])
    actual = _actual([(3, 5), (4, 5), (5, 5), (6, 6)])  # 基本贴合
    assert svc.compute_deviation_brief(expected, actual, next_chapter=7) is None


def test_compute_deviation_brief_insufficient_data_returns_none():
    svc = EmotionDeviationService()
    expected = _expected([5, 5, 6, 7])
    actual = _actual([(3, 2)])  # 仅 1 个可比对章节
    assert svc.compute_deviation_brief(expected, actual, next_chapter=4) is None


def test_compute_deviation_brief_empty_inputs_returns_none():
    svc = EmotionDeviationService()
    assert svc.compute_deviation_brief([], _actual([(1, 3)]), next_chapter=2) is None
    assert svc.compute_deviation_brief(_expected([5, 5]), [], next_chapter=2) is None


def test_compute_deviation_brief_single_outlier_keeps_correct_direction():
    """均值贴合但单章大幅偏「低」时，应判为低于规划（回归：旧逻辑只看 avg 会误判为偏高）。"""
    svc = EmotionDeviationService()
    expected = _expected([5, 5, 5, 5, 6])
    actual = _actual([(1, 5), (2, 5), (3, 5), (4, 1.5)])  # 仅末章骤降，均值 -0.875 贴合但单章 -3.5
    brief = svc.compute_deviation_brief(expected, actual, next_chapter=5)
    assert brief is not None  # 单章大幅偏差仍应触发
    assert "低于规划" in brief and "高于规划" not in brief


def test_compute_deviation_brief_threshold_boundary():
    """均值偏差跨过阈值(1.5)的边界行为。"""
    svc = EmotionDeviationService()
    expected = _expected([5, 5, 5, 5, 5, 6])
    # 均值偏差 -1.4 < 阈值，且无突兀单章 → 不出提示
    assert svc.compute_deviation_brief(
        expected, _actual([(2, 3.6), (3, 3.6), (4, 3.6), (5, 3.6)]), next_chapter=6
    ) is None
    # 均值偏差 -1.6 >= 阈值 → 出提示且方向为低于规划
    brief = svc.compute_deviation_brief(
        expected, _actual([(2, 3.4), (3, 3.4), (4, 3.4), (5, 3.4)]), next_chapter=6
    )
    assert brief is not None and "低于规划" in brief


def test_compute_deviation_brief_skips_malformed_expected_points():
    """规划点缺失强度键时跳过，不得用 0.0 兜底制造虚假偏差。"""
    svc = EmotionDeviationService()
    # ch1-4 缺 intensity 键（应跳过），仅 ch5/6 有效；实际只有 ch5/6 → 可比对不足 → None
    expected = [{"chapter_number": i} for i in range(1, 5)] + [
        {"chapter_number": 5, "emotion_intensity": 5},
        {"chapter_number": 6, "emotion_intensity": 5},
    ]
    actual = _actual([(1, 9), (2, 9), (3, 9), (4, 9), (5, 5)])
    # 只有 ch5 能匹配到有效规划点 → matched < 2 → None（若误用 0.0 兜底则会判为巨幅偏高）
    assert svc.compute_deviation_brief(expected, actual, next_chapter=6) is None


# ----------------------------------------------------------------- 聚合(峰值)
def test_aggregate_intensity_by_chapter_takes_peak_and_sanitizes():
    rows = [
        SimpleNamespace(chapter_number=1, emotion_intensity=5, emotion="喜悦"),
        SimpleNamespace(chapter_number=1, emotion_intensity=8, emotion="愤怒"),  # 同章取峰值
        SimpleNamespace(chapter_number=2, emotion_intensity=3, emotion="平静"),
        SimpleNamespace(chapter_number=2, emotion_intensity=None, emotion="x"),  # None 跳过
        SimpleNamespace(chapter_number=3, emotion_intensity=15, emotion="惊讶"),  # 越界夹回 10
    ]
    curve = EmotionDeviationService._aggregate_intensity_by_chapter(rows)
    assert curve == [
        {"chapter_number": 1, "intensity": 8.0, "emotion": "愤怒"},
        {"chapter_number": 2, "intensity": 3.0, "emotion": "平静"},
        {"chapter_number": 3, "intensity": 10.0, "emotion": "惊讶"},
    ]


# ----------------------------------------------------------------- 规划曲线
def test_build_expected_curve_basic_and_degrades():
    svc = EmotionDeviationService()
    curve = svc.build_expected_curve(total_chapters=30)
    assert len(curve) == 30
    assert all("emotion_intensity" in p and "chapter_number" in p for p in curve)
    # 非法入参降级为空
    assert svc.build_expected_curve(total_chapters=0) == []


# ----------------------------------------------------------------- DB 读取
async def _seed_states(session, rows):
    # CharacterState.id 为纯 BigInteger 主键(非 sqlite Integer 变体)，sqlite 下不自增，显式赋值
    for idx, (ch, name, intensity) in enumerate(rows, start=1):
        session.add(CharacterState(
            id=idx, project_id="p1", character_id=idx, character_name=name,
            chapter_number=ch, emotion="平静", emotion_intensity=intensity,
        ))
    await session.commit()


def test_build_actual_intensity_curve_from_character_state():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed_states(session, [
                (1, "甲", 4), (1, "乙", 7),   # 第1章峰值 7
                (2, "甲", 3),                  # 第2章 3
                (5, "甲", 6),                  # before_chapter=5 时应被排除(>=5)
            ])
            svc = EmotionDeviationService()
            curve = await svc.build_actual_intensity_curve("p1", before_chapter=5, session=session)
            assert curve == [
                {"chapter_number": 1, "intensity": 7.0, "emotion": "平静"},
                {"chapter_number": 2, "intensity": 3.0, "emotion": "平静"},
            ]
        await engine.dispose()
    asyncio.run(_run())


def test_build_brief_end_to_end_flags_below_plan():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            # 第4-9章实际情绪强度全部贴地(1)，远低于三幕结构 act2 的规划强度
            await _seed_states(session, [(ch, "主角", 1) for ch in range(4, 10)])
            svc = EmotionDeviationService()
            brief = await svc.build_brief(
                project_id="p1", total_chapters=12, next_chapter=10, session=session,
            )
            assert brief is not None
            assert "低于规划" in brief
        await engine.dispose()
    asyncio.run(_run())


def test_build_brief_degrades_without_states_returns_none():
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            svc = EmotionDeviationService()
            brief = await svc.build_brief(
                project_id="empty", total_chapters=20, next_chapter=6, session=session,
            )
            assert brief is None  # 无 CharacterState → 降级
        await engine.dispose()
    asyncio.run(_run())


def test_aggregate_drops_chapter_with_only_none_intensities():
    rows = [
        SimpleNamespace(chapter_number=2, emotion_intensity=None, emotion="x"),
        SimpleNamespace(chapter_number=2, emotion_intensity=None, emotion="y"),
    ]
    assert EmotionDeviationService._aggregate_intensity_by_chapter(rows) == []


def test_build_brief_insufficient_states_returns_none():
    """仅 1 章 CharacterState → 可比对不足 → None（端到端）。"""
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed_states(session, [(3, "主角", 2)])
            brief = await EmotionDeviationService().build_brief(
                project_id="p1", total_chapters=20, next_chapter=10, session=session,
            )
            assert brief is None
        await engine.dispose()
    asyncio.run(_run())


def test_build_brief_empty_expected_curve_returns_none():
    """规划曲线为空(total_chapters=0)时，即便有实际数据也降级 None。"""
    async def _run():
        engine, Session = _make_sessionmaker()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as session:
            await _seed_states(session, [(1, "甲", 3), (2, "甲", 3)])
            brief = await EmotionDeviationService().build_brief(
                project_id="p1", total_chapters=0, next_chapter=5, session=session,
            )
            assert brief is None
        await engine.dispose()
    asyncio.run(_run())


def test_build_brief_swallows_exceptions_returns_none():
    """内部异常不得外泄到生成流程。"""
    async def _run():
        svc = EmotionDeviationService()

        async def _boom(*args, **kwargs):
            raise RuntimeError("db down")

        svc.build_actual_intensity_curve = _boom  # 注入异常
        brief = await svc.build_brief(project_id="p1", total_chapters=20, next_chapter=6)
        assert brief is None
    asyncio.run(_run())


def test_prefetch_combines_guidance_and_deviation():
    """prefetch_trajectory_context 合并指导文本与偏差提示的拼接/降级逻辑。"""
    from app.services.trajectory_analysis_service import TrajectoryAnalysisService

    async def _call(guidance, deviation):
        svc = TrajectoryAnalysisService()

        async def _g(**kwargs):
            return guidance

        async def _d(**kwargs):
            return deviation

        svc._build_guidance_text = _g
        svc._build_deviation_brief = _d
        return await svc.prefetch_trajectory_context(
            project_id="p1", project=object(), chapter_number=5
        )

    async def _run():
        # 两者都有 → 用空行拼接
        both = await _call("指导文本", "偏差提示")
        assert both == "指导文本\n\n偏差提示"
        # 仅偏差 → 单独返回
        assert await _call(None, "偏差提示") == "偏差提示"
        # 仅指导 → 单独返回
        assert await _call("指导文本", None) == "指导文本"
        # 都无 → None
        assert await _call(None, None) is None
    asyncio.run(_run())
