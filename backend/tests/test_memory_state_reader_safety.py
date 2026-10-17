"""Latest-state selection must happen after adopted-source validation."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services import memory_layer_service as module


def test_newer_invalid_state_does_not_hide_an_older_valid_state(monkeypatch):
    invalid = SimpleNamespace(id=30, chapter_number=8, character_name="林砚", valid=False)
    valid = SimpleNamespace(id=20, chapter_number=7, character_name="林砚", valid=True)
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [invalid, valid]))))
    async def filter_rows(db, rows, project, before):
        assert db is session and project == "p" and before == 10
        assert rows == [invalid, valid]
        return [row for row in rows if row.valid]
    monkeypatch.setattr(module, "filter_current_rows", filter_rows)
    result = asyncio.run(module.MemoryLayerService(session).get_all_character_states("p", 9))
    assert result == [valid]
    query = str(session.execute.await_args.args[0])
    assert "character_states.chapter_number <=" in query
    assert "ORDER BY character_states.chapter_number DESC, character_states.id DESC" in query
    assert "max(" not in query.lower()


def test_same_chapter_states_are_deduplicated_by_newest_valid_id(monkeypatch):
    newest = SimpleNamespace(id=30, chapter_number=8, character_name="林砚")
    duplicate = SimpleNamespace(id=29, chapter_number=8, character_name="林砚")
    other = SimpleNamespace(id=20, chapter_number=7, character_name="师姐")
    older = SimpleNamespace(id=10, chapter_number=6, character_name="林砚")
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [newest, duplicate, other, older]))))
    monkeypatch.setattr(module, "filter_current_rows", AsyncMock(return_value=[newest, duplicate, other, older]))
    result = asyncio.run(module.MemoryLayerService(session).get_all_character_states("p", 9))
    assert result == [newest, other]
