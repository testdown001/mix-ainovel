"""writer_progress 三个 REST 端点的鉴权回归。

这三个端点原先完全没有鉴权：GET 会吐出 `last_output_preview`——正在生成的**正文
片段**，拿到 project_id 就能读别人的稿子；pause/resume 能改写别人进度对象的状态并
广播给其 WebSocket 订阅者。同侧的 WebSocket 端点一直校验 token + 归属，只有 REST
三兄弟漏了，所以这里逐个钉住：非属主一律 404（不泄露项目是否存在），属主可用。
"""
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.models.user_quota  # noqa: F401  触发 mapper 注册
from app.api.routers import writer_progress
from app.core.dependencies import get_current_user
from app.db.session import get_session
from app.models.novel import NovelProject
from app.schemas.user import UserInDB
from app.services.writer_progress_service import progress_service

OWNER = UserInDB(id=1, username="owner", hashed_password="x")
INTRUDER = UserInDB(id=2, username="intruder", hashed_password="x")
PROJECT_ID = "proj-progress-1"


def _build_client(db_session, user_holder):
    test_app = FastAPI()
    test_app.include_router(writer_progress.router)

    async def _override_session():
        yield db_session

    async def _override_user():
        return user_holder["user"]

    test_app.dependency_overrides[get_session] = _override_session
    test_app.dependency_overrides[get_current_user] = _override_user
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


@pytest.fixture(autouse=True)
def _clean_progress_cache():
    progress_service._progress_cache.clear()
    yield
    progress_service._progress_cache.clear()


async def _seed(db_session):
    db_session.add(NovelProject(id=PROJECT_ID, user_id=OWNER.id, title="属主的项目"))
    await db_session.commit()


@pytest.mark.asyncio
async def test_intruder_cannot_read_progress_preview(db_session):
    await _seed(db_session)
    progress = await progress_service.create_progress(PROJECT_ID, 1, "第一章")
    progress.last_output_preview = "属主未公开的正文片段"

    holder = {"user": INTRUDER}
    async with _build_client(db_session, holder) as client:
        resp = await client.get(f"/api/writer/progress/{PROJECT_ID}/1")
    assert resp.status_code == 404
    assert "正文片段" not in resp.text


@pytest.mark.asyncio
async def test_owner_can_read_progress(db_session):
    await _seed(db_session)
    progress = await progress_service.create_progress(PROJECT_ID, 1, "第一章")
    progress.last_output_preview = "属主自己的正文片段"

    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        resp = await client.get(f"/api/writer/progress/{PROJECT_ID}/1")
    assert resp.status_code == 200
    assert resp.json()["last_output_preview"] == "属主自己的正文片段"


@pytest.mark.asyncio
async def test_intruder_cannot_pause_or_resume(db_session):
    await _seed(db_session)
    await progress_service.create_progress(PROJECT_ID, 1, "第一章")

    holder = {"user": INTRUDER}
    async with _build_client(db_session, holder) as client:
        pause = await client.post(f"/api/writer/progress/{PROJECT_ID}/1/pause")
        resume = await client.post(f"/api/writer/progress/{PROJECT_ID}/1/resume")

    assert pause.status_code == 404
    assert resume.status_code == 404
    # 状态没有被外人改动过
    assert (await progress_service.get_progress(PROJECT_ID, 1)).status == "running"


@pytest.mark.asyncio
async def test_owner_can_pause_and_resume(db_session):
    await _seed(db_session)
    await progress_service.create_progress(PROJECT_ID, 1, "第一章")

    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        pause = await client.post(f"/api/writer/progress/{PROJECT_ID}/1/pause")
        assert pause.status_code == 200
        assert pause.json() == {"success": True}
        assert (await progress_service.get_progress(PROJECT_ID, 1)).status == "paused"

        resume = await client.post(f"/api/writer/progress/{PROJECT_ID}/1/resume")
        assert resume.status_code == 200
        assert (await progress_service.get_progress(PROJECT_ID, 1)).status == "running"


@pytest.mark.asyncio
async def test_unknown_project_is_404_not_500(db_session):
    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        resp = await client.get("/api/writer/progress/does-not-exist/1")
    assert resp.status_code == 404
