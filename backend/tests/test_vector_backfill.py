"""向量补录测试：rebuild_project_rag 增量筛选 / 端点薄壳回归 / backfill_vectors CLI。

全部 embedding / ingest 出口均被 mock，零外部调用。
"""
import argparse
import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  触发全部 mapper 注册
from app.db.base import Base
from app.models.novel import Chapter, ChapterVersion, NovelProject
from app.services import rag_rebuild_service
from app.services.chapter_post_processor import ChapterPostProcessor, compute_ingest_hash
from app.services.rag_rebuild_service import rebuild_project_rag


# ---------------------------------------------------------------------------
# 播种与 mock 辅助
# ---------------------------------------------------------------------------
async def _seed_project(session, *, project_id=None, user_id=1, title="测试小说"):
    project = NovelProject(id=project_id or str(uuid.uuid4()), user_id=user_id, title=title)
    session.add(project)
    await session.flush()
    return project


async def _seed_chapter(session, project_id, number, *, content, summary=None, ingest_hash=None):
    """播一章（含选中版本）。ingest_hash="match" 表示写入与当前内容一致的 hash。"""
    chapter = Chapter(
        project_id=project_id,
        chapter_number=number,
        real_summary=summary,
        status="completed",
    )
    session.add(chapter)
    await session.flush()
    version = ChapterVersion(chapter_id=chapter.id, content=content)
    session.add(version)
    await session.flush()
    chapter.selected_version_id = version.id
    if ingest_hash == "match":
        # 无大纲时 title 回退为 第N章，与服务内的计算保持一致
        chapter.rag_ingest_hash = compute_ingest_hash(f"第{number}章", summary, content)
    elif ingest_hash is not None:
        chapter.rag_ingest_hash = ingest_hash
    await session.flush()
    return chapter


async def _seed_standard_project(session):
    """3 章标准场景：ch1 hash 匹配 / ch2 hash 缺失 / ch3 hash 过时。"""
    project = await _seed_project(session)
    await _seed_chapter(session, project.id, 1, content="第一章正文" * 10, ingest_hash="match")
    await _seed_chapter(session, project.id, 2, content="第二章正文" * 10, ingest_hash=None)
    await _seed_chapter(session, project.id, 3, content="第三章正文" * 10, ingest_hash="stale-hash")
    await session.commit()
    return project


def _install_ingest_recorder(monkeypatch, *, fail_chapters=()):
    """替换 ChapterPostProcessor.ingest_chapter，记录调用并可按章号注入失败。"""
    calls = []

    async def fake_ingest(self, *, project_id, chapter_number, title, content, summary,
                          user_id, sync_bm25=False):
        if chapter_number in fail_chapters:
            raise RuntimeError(f"模拟章节 {chapter_number} 入库失败")
        calls.append({
            "project_id": project_id,
            "chapter_number": chapter_number,
            "title": title,
            "user_id": user_id,
            "sync_bm25": sync_bm25,
        })
        return "fake-hash"

    monkeypatch.setattr(ChapterPostProcessor, "ingest_chapter", fake_ingest)
    return calls


class _DummyIngestService:
    """替身 ChapterIngestionService（过期章节删除路径）。"""

    deleted = []

    def __init__(self, *, llm_service, vector_store=None):
        pass

    async def delete_chapters(self, project_id, chapter_numbers):
        _DummyIngestService.deleted.append((project_id, list(chapter_numbers)))


# ---------------------------------------------------------------------------
# 1. 公共服务函数：增量筛选
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_incremental_selects_missing_and_changed(db_session, monkeypatch):
    project = await _seed_standard_project(db_session)
    calls = _install_ingest_recorder(monkeypatch)

    stats = await rebuild_project_rag(db_session, object(), project.id, user_id=7)

    assert stats["chapters"] == 3
    assert stats["pending"] == [2, 3]          # hash 缺失/过时入选
    assert stats["indexed"] == 2
    assert stats["skipped"] == 1               # hash 匹配跳过
    assert stats["failed"] == 0
    assert stats["mode"] == "incremental"
    assert [c["chapter_number"] for c in calls] == [2, 3]
    assert all(c["user_id"] == 7 for c in calls)
    assert all(c["sync_bm25"] is False for c in calls)  # skip_bm25 默认 True


@pytest.mark.asyncio
async def test_force_full_selects_all(db_session, monkeypatch):
    project = await _seed_standard_project(db_session)
    calls = _install_ingest_recorder(monkeypatch)

    stats = await rebuild_project_rag(db_session, object(), project.id, force_full=True)

    assert stats["pending"] == [1, 2, 3]
    assert stats["indexed"] == 3
    assert stats["skipped"] == 0
    assert stats["mode"] == "full"
    assert [c["chapter_number"] for c in calls] == [1, 2, 3]


@pytest.mark.asyncio
async def test_dry_run_zero_ingest_calls(db_session, monkeypatch):
    project = await _seed_standard_project(db_session)
    calls = _install_ingest_recorder(monkeypatch)

    stats = await rebuild_project_rag(db_session, object(), project.id, dry_run=True)

    assert stats["dry_run"] is True
    assert stats["pending"] == [2, 3]
    assert stats["indexed"] == 0
    assert stats["skipped"] == 1
    assert calls == []  # 零 ingest / embedding 调用


@pytest.mark.asyncio
async def test_stale_chapters_removed_and_hash_cleared(db_session, monkeypatch):
    project = await _seed_standard_project(db_session)
    # 第 99 章：已索引 hash 但无正文（可索引集合之外）→ 过期
    stale = Chapter(project_id=project.id, chapter_number=99, rag_ingest_hash="ghost")
    db_session.add(stale)
    await db_session.commit()

    _install_ingest_recorder(monkeypatch)
    _DummyIngestService.deleted = []
    monkeypatch.setattr(rag_rebuild_service, "ChapterIngestionService", _DummyIngestService)

    stats = await rebuild_project_rag(db_session, object(), project.id)

    assert stats["stale"] == [99]
    assert stats["removed"] == 1
    assert _DummyIngestService.deleted == [(project.id, [99])]
    result = await db_session.execute(
        select(Chapter.rag_ingest_hash).where(
            Chapter.project_id == project.id, Chapter.chapter_number == 99
        )
    )
    assert result.scalar_one() is None


@pytest.mark.asyncio
async def test_chapter_failure_raises_by_default(db_session, monkeypatch):
    project = await _seed_standard_project(db_session)
    _install_ingest_recorder(monkeypatch, fail_chapters={2})

    with pytest.raises(RuntimeError):  # 端点行为：异常直接抛出
        await rebuild_project_rag(db_session, object(), project.id)


@pytest.mark.asyncio
async def test_chapter_failure_continues_when_continue_on_error(db_session, monkeypatch):
    project = await _seed_standard_project(db_session)
    calls = _install_ingest_recorder(monkeypatch, fail_chapters={2})

    stats = await rebuild_project_rag(
        db_session, object(), project.id, continue_on_error=True
    )

    assert stats["failed"] == 1
    assert stats["indexed"] == 1               # 第 3 章不受第 2 章失败影响
    assert [c["chapter_number"] for c in calls] == [3]
    assert stats["failures"][0]["chapter_number"] == 2
    assert "模拟章节 2" in stats["failures"][0]["error"]


@pytest.mark.asyncio
async def test_progress_cb_receives_events(db_session, monkeypatch):
    project = await _seed_standard_project(db_session)
    _install_ingest_recorder(monkeypatch, fail_chapters={2})
    events = []

    await rebuild_project_rag(
        db_session, object(), project.id,
        continue_on_error=True, progress_cb=events.append,
    )

    kinds = [(e["event"], e["chapter_number"]) for e in events]
    assert ("ingest_start", 2) in kinds
    assert ("ingest_failed", 2) in kinds
    assert ("ingest_done", 3) in kinds


# ---------------------------------------------------------------------------
# 2. 端点薄壳回归（响应契约不变）
# ---------------------------------------------------------------------------
def test_rebuild_rag_route_binding():
    """路由绑定回归：防装饰器错绑（新函数插入 @router 与函数之间的历史教训）。"""
    from app.api.routers import writer

    route = next(
        r for r in writer.router.routes
        if getattr(r, "path", "") == "/api/writer/novels/{project_id}/rag/rebuild"
    )
    assert route.endpoint is writer.rebuild_rag
    assert route.methods == {"POST"}


@pytest.mark.asyncio
async def test_rebuild_rag_endpoint_response_contract(db_session, monkeypatch):
    from app.api.routers import writer

    project = await _seed_standard_project(db_session)
    calls = _install_ingest_recorder(monkeypatch)
    monkeypatch.setattr(writer, "create_vector_store_or_none", lambda: object())

    response = await writer.rebuild_rag(
        project_id=project.id,
        session=db_session,
        current_user=SimpleNamespace(id=1),
    )

    # 响应体键集与语义与抽取前完全一致
    assert response == {
        "indexed_chapters": 2,
        "skipped_chapters": 1,
        "removed_chapters": 0,
        "mode": "incremental",
        "bm25_indexed": False,
    }
    assert [c["chapter_number"] for c in calls] == [2, 3]
    assert all(c["user_id"] == 1 for c in calls)


@pytest.mark.asyncio
async def test_rebuild_rag_endpoint_guards(db_session, monkeypatch):
    from fastapi import HTTPException

    from app.api.routers import writer

    project = await _seed_standard_project(db_session)

    # 非所有者 → 404
    with pytest.raises(HTTPException) as exc_info:
        await writer.rebuild_rag(
            project_id=project.id,
            session=db_session,
            current_user=SimpleNamespace(id=999),
        )
    assert exc_info.value.status_code == 404

    # 向量库未启用 → 400
    monkeypatch.setattr(writer, "create_vector_store_or_none", lambda: None)
    with pytest.raises(HTTPException) as exc_info:
        await writer.rebuild_rag(
            project_id=project.id,
            session=db_session,
            current_user=SimpleNamespace(id=1),
        )
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# 3. backfill_vectors CLI
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def cli_session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(bind=engine, expire_on_commit=False)
    await engine.dispose()


def _cli_args(**overrides):
    defaults = {"project_id": None, "user_id": None, "dry_run": False, "force_full": False}
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _setup_cli(monkeypatch, session_factory):
    import backfill_vectors

    monkeypatch.setattr(backfill_vectors, "_SESSION_FACTORY", session_factory)
    monkeypatch.setattr(backfill_vectors, "_check_vector_store", lambda: object())
    return backfill_vectors


async def _seed_cli_projects(session_factory):
    """两个项目：A（用户1）待补 2 章，B（用户2）全部已最新。"""
    async with session_factory() as session:
        project_a = await _seed_project(session, user_id=1, title="项目A")
        await _seed_chapter(session, project_a.id, 1, content="A1" * 20, ingest_hash=None)
        await _seed_chapter(session, project_a.id, 2, content="A2" * 20, ingest_hash="stale")
        project_b = await _seed_project(session, user_id=2, title="项目B")
        await _seed_chapter(session, project_b.id, 1, content="B1" * 20, ingest_hash="match")
        await session.commit()
        return project_a.id, project_b.id


@pytest.mark.asyncio
async def test_cli_dry_run_counts_pending_with_zero_ingest(
    cli_session_factory, monkeypatch, capsys
):
    backfill_vectors = _setup_cli(monkeypatch, cli_session_factory)
    await _seed_cli_projects(cli_session_factory)
    calls = _install_ingest_recorder(monkeypatch)

    exit_code = await backfill_vectors.run_backfill(_cli_args(dry_run=True))

    assert exit_code == 0
    assert calls == []  # dry-run 零 ingest / embedding 调用
    output = capsys.readouterr().out
    assert "共 2 个项目待处理" in output
    assert "待补 2 章" in output
    assert "待补 2 章（项目级失败 0 个）" in output  # 汇总总数 = 2+0


@pytest.mark.asyncio
async def test_cli_real_run_stats_and_filters(cli_session_factory, monkeypatch, capsys):
    backfill_vectors = _setup_cli(monkeypatch, cli_session_factory)
    project_a_id, _ = await _seed_cli_projects(cli_session_factory)
    calls = _install_ingest_recorder(monkeypatch)

    # --user-id 过滤：只跑用户 1 的项目 A
    exit_code = await backfill_vectors.run_backfill(_cli_args(user_id=1))

    assert exit_code == 0
    assert [c["chapter_number"] for c in calls] == [1, 2]
    assert all(c["project_id"] == project_a_id for c in calls)
    output = capsys.readouterr().out
    assert "共 1 个项目待处理" in output
    assert "indexed=2, skipped=0, failed=0, removed=0" in output


@pytest.mark.asyncio
async def test_cli_unknown_project_id_is_human_error(cli_session_factory, monkeypatch):
    backfill_vectors = _setup_cli(monkeypatch, cli_session_factory)
    await _seed_cli_projects(cli_session_factory)

    with pytest.raises(backfill_vectors.CLIError, match="项目不存在"):
        await backfill_vectors.run_backfill(_cli_args(project_id="no-such-project"))


@pytest.mark.asyncio
async def test_cli_project_failure_does_not_abort_batch(
    cli_session_factory, monkeypatch, capsys
):
    backfill_vectors = _setup_cli(monkeypatch, cli_session_factory)
    project_a_id, project_b_id = await _seed_cli_projects(cli_session_factory)

    attempted = []

    async def fake_rebuild(session, llm_service, project_id, **kwargs):
        attempted.append(project_id)
        if project_id == project_a_id:
            raise RuntimeError("模拟项目级崩溃")
        return {
            "chapters": 1, "pending": [], "stale": [], "indexed": 0, "skipped": 1,
            "removed": 0, "failed": 0, "failures": [],
            "mode": "incremental", "bm25_indexed": False, "dry_run": False,
        }

    monkeypatch.setattr(
        "app.services.rag_rebuild_service.rebuild_project_rag", fake_rebuild
    )

    exit_code = await backfill_vectors.run_backfill(_cli_args())

    # A 崩溃后 B 仍被处理（updated_at 同秒时按随机 uuid 排序，只断言集合）
    assert set(attempted) == {project_a_id, project_b_id}
    assert exit_code == 1                             # 有失败 → 退出码 1
    output = capsys.readouterr().out
    assert "项目级失败" in output
    assert "模拟项目级崩溃" in output


@pytest.mark.asyncio
async def test_cli_chapter_failures_yield_exit_code_1(cli_session_factory, monkeypatch):
    backfill_vectors = _setup_cli(monkeypatch, cli_session_factory)
    await _seed_cli_projects(cli_session_factory)
    _install_ingest_recorder(monkeypatch, fail_chapters={2})

    exit_code = await backfill_vectors.run_backfill(_cli_args())

    assert exit_code == 1  # 项目 A 第 2 章失败 → 整批退出码 1


@pytest.mark.asyncio
async def test_cli_force_full_passthrough(cli_session_factory, monkeypatch):
    backfill_vectors = _setup_cli(monkeypatch, cli_session_factory)
    await _seed_cli_projects(cli_session_factory)
    calls = _install_ingest_recorder(monkeypatch)

    exit_code = await backfill_vectors.run_backfill(_cli_args(force_full=True))

    assert exit_code == 0
    # force_full 下项目 B 已最新的 1 章也被重建：A 2 章 + B 1 章
    assert len(calls) == 3
