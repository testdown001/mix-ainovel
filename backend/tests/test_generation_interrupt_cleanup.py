"""客户端断开后不留「幽灵生成中」章节。

生成开工时 `chapter.status = 'generating'` 会立即提交；`CancelledError`（客户端关页
面/切路由/网络中断，SSE 路径还会连带 cancel 生产者任务）不是 `Exception` 子类，此前
两个同步入口的 `except HTTPException/Exception` 都接不住它，于是生成真的停了、状态
却永远停在 generating：前端画着转圈 + 每 10 秒轮询，用户看到「卡死」，然后刷新重点
一次——我们白烧一次上游调用。

这里钉住：断开后状态必须落到 failed，且补偿失败不许遮蔽取消的传播。
"""
import asyncio

import pytest

import app.models  # noqa: F401  触发全部 mapper 注册
from app.api.routers import writer
from app.models.novel import Chapter, ChapterOutline, NovelProject
from app.schemas.novel import AdvancedGenerateRequest, FlowConfig
from app.schemas.user import UserInDB

OWNER = UserInDB(id=1, username="owner", hashed_password="x")
PROJECT_ID = "proj-interrupt-1"


class _SessionFactory:
    """替身 AsyncSessionLocal：交出测试会话且不关闭它。"""

    def __init__(self, session):
        self.session = session
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_exc):
        return False


async def _seed(db_session):
    db_session.add(NovelProject(id=PROJECT_ID, user_id=OWNER.id, title="断线项目"))
    db_session.add(
        ChapterOutline(project_id=PROJECT_ID, chapter_number=1, title="第一章", summary="开篇")
    )
    db_session.add(Chapter(project_id=PROJECT_ID, chapter_number=1, status="generating"))
    await db_session.commit()


async def _chapter_status(db_session):
    chapter = (
        await db_session.execute(
            Chapter.__table__.select().where(Chapter.project_id == PROJECT_ID)
        )
    ).first()
    return chapter.status


@pytest.mark.asyncio
async def test_mark_interrupted_writes_failed_status(db_session, monkeypatch):
    await _seed(db_session)
    monkeypatch.setattr(writer, "AsyncSessionLocal", _SessionFactory(db_session))

    await writer._mark_chapter_interrupted_safely(PROJECT_ID, 1)

    assert await _chapter_status(db_session) == "failed"


@pytest.mark.asyncio
async def test_mark_interrupted_swallows_failures(db_session, monkeypatch):
    """补偿本身失败只能记日志：它跑在取消传播的路上，抛出会遮蔽真正的取消。"""

    class _BrokenFactory:
        def __call__(self):
            raise RuntimeError("连接池已关闭")

    monkeypatch.setattr(writer, "AsyncSessionLocal", _BrokenFactory())
    await writer._mark_chapter_interrupted_safely(PROJECT_ID, 1)  # 不抛即通过


@pytest.mark.asyncio
async def test_unknown_chapter_is_noop(db_session, monkeypatch):
    monkeypatch.setattr(writer, "AsyncSessionLocal", _SessionFactory(db_session))
    await writer._mark_chapter_interrupted_safely("no-such-project", 7)


@pytest.mark.asyncio
async def test_sync_endpoint_marks_failed_on_client_disconnect(db_session, monkeypatch):
    """同步入口：CancelledError 必须先落状态再继续传播。"""
    await _seed(db_session)
    monkeypatch.setattr(writer, "AsyncSessionLocal", _SessionFactory(db_session))

    from app.agents import hybrid_executor

    class _CancellingExecutor:
        def __init__(self, session, user_id=None):
            pass

        def enable_agent_system(self):
            pass

        async def generate_chapter(self, **_kwargs):
            raise asyncio.CancelledError()

    monkeypatch.setattr(hybrid_executor, "HybridExecutor", _CancellingExecutor)

    class _NoBackgroundTasks:
        def add_task(self, *_args, **_kwargs):
            raise AssertionError("取消路径不应排队后续任务")

    request = AdvancedGenerateRequest(
        project_id=PROJECT_ID,
        chapter_number=1,
        flow_config=FlowConfig(preset="fast"),
    )

    with pytest.raises(asyncio.CancelledError):
        await writer.advanced_generate_chapter(
            request=request,
            background_tasks=_NoBackgroundTasks(),
            session=db_session,
            current_user=OWNER,
        )

    assert await _chapter_status(db_session) == "failed"
