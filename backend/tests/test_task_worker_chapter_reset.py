"""异步 worker 失败时回写章节 generating→failed 的回归。

锁定：_reset_generating_chapters_to_failed 只把「本任务相关且仍 generating」的章节
置 failed，不动其它章节/其它状态——避免章节永久卡在 generating（前端一直"等待生成"）。
"""
import contextlib
from types import SimpleNamespace

import pytest
from sqlalchemy import select

import app.models  # noqa: F401  触发全部 mapper 注册
from app.models.novel import Chapter
from app.api.routers import task_worker
from app.api.routers.task_worker import _reset_generating_chapters_to_failed


def test_execute_route_bound_to_execute_task():
    """回归：/api/internal/tasks/execute 必须绑定到 execute_task 本身。
    曾因把 _reset_generating_chapters_to_failed 插到 @router.post 与 execute_task 之间，
    装饰器错绑到辅助函数→真正生成逻辑不被路由→worker 返回 None 撞 response_model→500。"""
    routes = task_worker.router.routes
    execute_routes = [r for r in routes if getattr(r, "endpoint", None) is task_worker.execute_task]
    assert execute_routes, "execute_task 未注册为路由（@router.post 可能被错绑到其它函数）"
    assert any(getattr(r, "path", "").endswith("/execute") for r in execute_routes)
    # 辅助函数绝不能成为任何路由的 endpoint
    assert all(
        getattr(r, "endpoint", None) is not _reset_generating_chapters_to_failed for r in routes
    )


@pytest.mark.asyncio
async def test_reset_only_targeted_generating_chapters(db_session, monkeypatch):
    db_session.add(Chapter(project_id="p1", chapter_number=1, status="generating"))
    db_session.add(Chapter(project_id="p1", chapter_number=2, status="successful"))
    db_session.add(Chapter(project_id="p1", chapter_number=3, status="generating"))
    await db_session.commit()

    @contextlib.asynccontextmanager
    async def fake_factory():
        yield db_session

    monkeypatch.setattr("app.api.routers.task_worker.AsyncSessionLocal", fake_factory)

    # 单章任务：只针对第 1 章
    req = SimpleNamespace(
        task_id="t1", task_type="chapter:generate", project_id="p1",
        chapter_number=1, chapter_numbers=None,
    )
    await _reset_generating_chapters_to_failed(req)

    rows = (
        await db_session.execute(
            select(Chapter).where(Chapter.project_id == "p1").order_by(Chapter.chapter_number)
        )
    ).scalars().all()
    statuses = {r.chapter_number: r.status for r in rows}
    # 第1章(目标且 generating)→failed；第2章(successful)不动；第3章(generating 但非本任务)不动
    assert statuses == {1: "failed", 2: "successful", 3: "generating"}


@pytest.mark.asyncio
async def test_reset_batch_and_noop_paths(db_session, monkeypatch):
    db_session.add(Chapter(project_id="p2", chapter_number=1, status="generating"))
    db_session.add(Chapter(project_id="p2", chapter_number=2, status="generating"))
    await db_session.commit()

    @contextlib.asynccontextmanager
    async def fake_factory():
        yield db_session

    monkeypatch.setattr("app.api.routers.task_worker.AsyncSessionLocal", fake_factory)

    # 非生成类任务：直接 no-op
    await _reset_generating_chapters_to_failed(
        SimpleNamespace(task_id="x", task_type="rag:retrieve", project_id="p2",
                        chapter_number=None, chapter_numbers=None)
    )
    # 批量任务：两章都翻转
    await _reset_generating_chapters_to_failed(
        SimpleNamespace(task_id="t2", task_type="chapter:batch_generate", project_id="p2",
                        chapter_number=None, chapter_numbers=[1, 2])
    )

    rows = (
        await db_session.execute(select(Chapter).where(Chapter.project_id == "p2"))
    ).scalars().all()
    assert all(r.status == "failed" for r in rows)
