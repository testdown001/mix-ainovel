"""TemporalStateService 单元测试（8 例）"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.temporal_state_service import TemporalStateService, WorldStateSnapshot


# ── helpers ──────────────────────────────────────────────────────────────

def _make_char_state(name, location=None, emotion=None, health="healthy", power_level=None, goals=None):
    return SimpleNamespace(
        character_name=name,
        location=location,
        emotion=emotion,
        health_status=health,
        power_level=power_level,
        current_goals=goals or [],
    )


# ── tests ────────────────────────────────────────────────────────────────

def test_snapshot_empty_project():
    """空项目返回空快照"""
    db = AsyncMock()
    service = TemporalStateService(db)

    async def _run():
        with patch.object(service, "_fetch_characters", new_callable=AsyncMock), \
             patch.object(service, "_fetch_events", new_callable=AsyncMock), \
             patch.object(service, "_fetch_causal_chains", new_callable=AsyncMock), \
             patch.object(service, "_fetch_story_time", new_callable=AsyncMock), \
             patch.object(service, "_fetch_foreshadowing", new_callable=AsyncMock):
            return await service.get_world_snapshot("proj1", 1)

    snapshot = asyncio.run(_run())
    assert isinstance(snapshot, WorldStateSnapshot)
    assert snapshot.characters == []
    assert snapshot.recent_events == []
    assert snapshot.pending_chains == []
    assert snapshot.relationship_network == ""


def test_snapshot_characters_with_involved_filter():
    """involved_characters 过滤正常工作"""
    db = AsyncMock()
    service = TemporalStateService(db)

    states = [
        _make_char_state("张三", location="京城", power_level="金丹期"),
        _make_char_state("李四", location="南荒"),
        _make_char_state("王五", location="东海"),
        _make_char_state("赵六", location="北境"),
        _make_char_state("孙七", location="西域"),
    ]

    async def fake_fetch_chars(project_id, chapter_number, involved_characters, snapshot):
        for s in states:
            snapshot.characters.append({"name": s.character_name, "location": s.location})
        if involved_characters:
            involved_set = set(involved_characters)
            primary = [c for c in snapshot.characters if c["name"] in involved_set]
            secondary = [c for c in snapshot.characters if c["name"] not in involved_set]
            snapshot.characters = primary + secondary[:3]

    async def _run():
        with patch.object(service, "_fetch_characters", side_effect=fake_fetch_chars), \
             patch.object(service, "_fetch_events", new_callable=AsyncMock), \
             patch.object(service, "_fetch_causal_chains", new_callable=AsyncMock), \
             patch.object(service, "_fetch_story_time", new_callable=AsyncMock), \
             patch.object(service, "_fetch_foreshadowing", new_callable=AsyncMock):
            return await service.get_world_snapshot(
                "proj1", 5, involved_characters=["张三", "李四"]
            )

    snapshot = asyncio.run(_run())
    names = [c["name"] for c in snapshot.characters]
    assert names[0] == "张三"
    assert names[1] == "李四"
    assert len(snapshot.characters) == 5  # 2 involved + 3 secondary


def test_snapshot_full_data():
    """全数据源聚合"""
    db = AsyncMock()
    service = TemporalStateService(db)

    async def fake_chars(pid, cn, ic, snap):
        snap.characters.append({"name": "主角", "location": "京城"})
        snap.power_landscape.append({"name": "主角", "power_level": "金丹期"})

    async def fake_events(pid, cn, snap):
        snap.recent_events.append({"chapter": 3, "event": "决战", "importance": 9})

    async def fake_chains(pid, snap):
        snap.pending_chains.append({"cause": "暗算", "cause_chapter": 2, "expected_effect": "复仇"})

    async def fake_time(pid, snap):
        snap.story_time = {"chapter_time_map": {"1": "第一天"}}

    async def fake_fs(pid, cn, snap):
        snap.foreshadowing_alerts["urgent"].append({"name": "黑玉", "description": "碎片来源"})

    async def _run():
        with patch.object(service, "_fetch_characters", side_effect=fake_chars), \
             patch.object(service, "_fetch_events", side_effect=fake_events), \
             patch.object(service, "_fetch_causal_chains", side_effect=fake_chains), \
             patch.object(service, "_fetch_story_time", side_effect=fake_time), \
             patch.object(service, "_fetch_foreshadowing", side_effect=fake_fs):
            return await service.get_world_snapshot("proj1", 5)

    snapshot = asyncio.run(_run())
    assert len(snapshot.characters) == 1
    assert len(snapshot.recent_events) == 1
    assert len(snapshot.pending_chains) == 1
    assert len(snapshot.foreshadowing_alerts["urgent"]) == 1
    assert snapshot.story_time["chapter_time_map"]["1"] == "第一天"
    assert len(snapshot.power_landscape) == 1


def test_snapshot_foreshadowing_classification():
    """urgent/due_soon/overdue 分类"""
    db = AsyncMock()
    service = TemporalStateService(db)

    async def fake_fs(pid, cn, snap):
        snap.foreshadowing_alerts["urgent"].append({"name": "紧急伏笔", "urgency": 9})
        snap.foreshadowing_alerts["due_soon"].append({"name": "临近伏笔", "urgency": 6})
        snap.foreshadowing_alerts["overdue"].append({"name": "逾期伏笔", "urgency": 5})

    async def _run():
        with patch.object(service, "_fetch_characters", new_callable=AsyncMock), \
             patch.object(service, "_fetch_events", new_callable=AsyncMock), \
             patch.object(service, "_fetch_causal_chains", new_callable=AsyncMock), \
             patch.object(service, "_fetch_story_time", new_callable=AsyncMock), \
             patch.object(service, "_fetch_foreshadowing", side_effect=fake_fs):
            return await service.get_world_snapshot("proj1", 10)

    snapshot = asyncio.run(_run())
    assert len(snapshot.foreshadowing_alerts["urgent"]) == 1
    assert len(snapshot.foreshadowing_alerts["due_soon"]) == 1
    assert len(snapshot.foreshadowing_alerts["overdue"]) == 1


def test_snapshot_partial_failure():
    """单个数据源异常时降级，其余正常"""
    db = AsyncMock()
    service = TemporalStateService(db)

    async def failing_events(pid, cn, snap):
        raise RuntimeError("DB timeout")

    async def ok_chars(pid, cn, ic, snap):
        snap.characters.append({"name": "主角"})

    async def _run():
        with patch.object(service, "_fetch_characters", side_effect=ok_chars), \
             patch.object(service, "_fetch_events", side_effect=failing_events), \
             patch.object(service, "_fetch_causal_chains", new_callable=AsyncMock), \
             patch.object(service, "_fetch_story_time", new_callable=AsyncMock), \
             patch.object(service, "_fetch_foreshadowing", new_callable=AsyncMock):
            return await service.get_world_snapshot("proj1", 5)

    snapshot = asyncio.run(_run())
    assert len(snapshot.characters) == 1
    assert snapshot.recent_events == []


def test_to_evidence_items_format():
    """EvidenceItem 的 source/score 格式正确"""
    snapshot = WorldStateSnapshot(
        characters=[{"name": "主角", "location": "京城", "emotion": "愤怒"}],
        foreshadowing_alerts={"urgent": [{"name": "伏笔A", "description": "重要"}], "due_soon": [], "overdue": []},
    )

    service = TemporalStateService.__new__(TemporalStateService)
    items = service.to_evidence_items(snapshot)

    assert len(items) >= 2
    for item in items:
        assert item.source == "state_rag"
        assert item.metadata.get("origin") == "temporal_snapshot"
        assert 0 < item.score <= 1.0


def test_to_evidence_items_priority_order():
    """紧迫伏笔排在前面"""
    snapshot = WorldStateSnapshot(
        characters=[{"name": "主角", "location": "京城"}],
        recent_events=[{"chapter": 3, "event": "决战"}],
        foreshadowing_alerts={
            "urgent": [{"name": "伏笔A", "description": "紧急"}],
            "due_soon": [],
            "overdue": [],
        },
    )

    service = TemporalStateService.__new__(TemporalStateService)
    items = service.to_evidence_items(snapshot)

    assert len(items) >= 2
    assert items[0].score >= items[-1].score  # 紧迫伏笔在前


def test_to_evidence_items_empty():
    """空快照返回空列表"""
    snapshot = WorldStateSnapshot()
    service = TemporalStateService.__new__(TemporalStateService)
    items = service.to_evidence_items(snapshot)
    assert items == []
