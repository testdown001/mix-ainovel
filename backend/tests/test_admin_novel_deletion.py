"""Exercise the real admin API and database, including protected AI-assisted works."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import func, select, text

from app.api.routers import admin
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, decode_access_token
from app.db.session import get_session
from app.models.novel import Chapter, ChapterOutline, ChapterVersion, NovelBlueprint, NovelProject
from app.models.user import User
from app.schemas.user import UserInDB
from app.services.cache_service import CacheService
from app.services.novel_service import NovelService
from app.services.admin_novel_deletion_service import _confirmation_key

ADMIN = UserInDB(id=99, username="admin", hashed_password="x", is_admin=True)


def client_for(db, holder):
    app = FastAPI()
    app.include_router(admin.router)

    async def session_override():
        yield db

    async def user_override():
        return holder["user"]

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_current_user] = user_override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def no_external_cleanup(monkeypatch):
    monkeypatch.setattr(CacheService, "invalidate_project_cascade", AsyncMock())
    monkeypatch.setattr(NovelService, "_invalidate_chapter_related_cache", lambda *args: None)
    monkeypatch.setattr(NovelService, "_delete_chapter_vectors", AsyncMock())
    monkeypatch.setattr("app.services.cover_storage_service.delete_cover_file", lambda _: False)


async def seed(db):
    await db.execute(text("PRAGMA foreign_keys=ON"))
    db.add_all([
        User(id=1, username="real-user", hashed_password="x"),
        User(id=2, username="bench@local", hashed_password="x"),
    ])
    await db.flush()
    db.add_all([
        NovelProject(id="user-book", user_id=1, title="[bench-test] 用户 AI 小说", ai_assisted=True),
        NovelProject(id="test-book", user_id=2, title="测试书", creation_source="ai_test"),
        NovelProject(id="system-book", user_id=2, title="系统示例", creation_source="system"),
        NovelProject(id="unknown-book", user_id=2, title="来源未知", creation_source="unknown"),
    ])
    await db.commit()


async def first(client, project="test-book"):
    return await client.post(f"/api/admin/novel-projects/{project}/deletion-confirmation", json={"confirmation": "删除"})


async def final(client, token, project="test-book", confirmation="删除"):
    return await client.request("DELETE", f"/api/admin/novel-projects/{project}", json={
        "confirmation": confirmation, "confirmation_token": token,
    })


@pytest.mark.asyncio
async def test_summary_source_and_user_creation_cannot_be_ai_test(db_session):
    await seed(db_session)
    project = await NovelService(db_session).create_project(1, "系统测试", "AI 自动写作")
    assert project.creation_source == "user"
    async with client_for(db_session, {"user": ADMIN}) as client:
        rows = {row["id"]: row for row in (await client.get("/api/admin/novel-projects")).json()}
    assert rows["test-book"]["can_delete"] is True
    assert rows["system-book"]["can_delete"] is True
    assert rows["user-book"]["can_delete"] is False
    assert rows["unknown-book"]["can_delete"] is False
    assert rows[project.id]["creation_source"] == "user"


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["user-book", "unknown-book"])
async def test_protected_projects_rejected_even_with_valid_ticket(db_session, source):
    await seed(db_session)
    async with client_for(db_session, {"user": ADMIN}) as client:
        assert (await first(client, source)).status_code == 403
        token = (await first(client)).json()["confirmation_token"]
        with pytest.raises(HTTPException) as error:
            decode_access_token(token)
        assert error.value.status_code == 401
        assert (await final(client, token, source)).status_code == 403
    assert await db_session.get(NovelProject, source) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("project", ["test-book", "system-book"])
async def test_two_steps_delete_only_target_and_cascade(db_session, project):
    await seed(db_session)
    db_session.add_all([
        NovelBlueprint(project_id=project, title="蓝图"),
        ChapterOutline(project_id=project, chapter_number=1, title="第一章"),
    ])
    chapter = Chapter(project_id=project, chapter_number=1)
    db_session.add(chapter)
    await db_session.flush()
    version = ChapterVersion(chapter_id=chapter.id, content="正文")
    db_session.add(version)
    await db_session.flush()
    chapter.selected_version_id = version.id
    await db_session.commit()
    async with client_for(db_session, {"user": ADMIN}) as client:
        ticket = (await first(client, project)).json()
        assert ticket["expires_in"] == 300
        assert await db_session.get(NovelProject, project) is not None
        assert (await final(client, ticket["confirmation_token"], project)).status_code == 204
        assert (await final(client, ticket["confirmation_token"], project)).status_code == 404
    assert await db_session.scalar(select(func.count(NovelProject.id))) == 3
    for model in [Chapter, ChapterVersion, ChapterOutline, NovelBlueprint]:
        assert await db_session.scalar(select(func.count()).select_from(model)) == 0
    assert await db_session.get(NovelProject, "user-book") is not None


@pytest.mark.asyncio
async def test_both_inputs_required_and_token_cannot_be_skipped(db_session):
    await seed(db_session)
    async with client_for(db_session, {"user": ADMIN}) as client:
        for value in ["", "delete", " 删除", "确认"]:
            response = await client.post("/api/admin/novel-projects/test-book/deletion-confirmation", json={"confirmation": value})
            assert response.status_code == 422
        token = (await first(client)).json()["confirmation_token"]
        assert (await final(client, token, confirmation="确认")).status_code == 422
        assert (await client.request("DELETE", "/api/admin/novel-projects/test-book", json={"confirmation": "删除"})).status_code == 422
        for token_value in ["forged", create_access_token(ADMIN.id)]:
            assert (await final(client, token_value)).status_code == 403
    assert await db_session.get(NovelProject, "test-book") is not None


@pytest.mark.asyncio
async def test_confirmation_bound_to_admin_project_expiry_and_source(db_session):
    await seed(db_session)
    holder = {"user": ADMIN}
    async with client_for(db_session, holder) as client:
        token = (await first(client)).json()["confirmation_token"]
        assert (await final(client, token, "system-book")).status_code == 403
        holder["user"] = ADMIN.model_copy(update={"id": 100})
        assert (await final(client, token)).status_code == 403
        holder["user"] = ADMIN
        claims = jwt.get_unverified_claims(token)
        claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=5)
        expired = jwt.encode(claims, _confirmation_key(), algorithm=settings.jwt_algorithm)
        assert (await final(client, expired)).status_code == 403
        project = await db_session.get(NovelProject, "test-book")
        project.creation_source = "user"
        await db_session.commit()
        assert (await final(client, token)).status_code == 403
    assert await db_session.get(NovelProject, "test-book") is not None


@pytest.mark.asyncio
async def test_admin_required_and_missing_project_404(db_session):
    await seed(db_session)
    holder = {"user": ADMIN}
    async with client_for(db_session, holder) as client:
        assert (await first(client, "missing")).status_code == 404
        token = (await first(client)).json()["confirmation_token"]
        holder["user"] = ADMIN.model_copy(update={"is_admin": False})
        assert (await first(client)).status_code == 403
        assert (await final(client, token)).status_code == 403


async def batch_first(client, ids=("test-book", "system-book"), confirmation="删除"):
    return await client.post("/api/admin/novel-projects/deletion-confirmation", json={
        "project_ids": list(ids), "confirmation": confirmation,
    })


async def batch_final(client, token, ids=("test-book", "system-book"), confirmation="删除"):
    return await client.request("DELETE", "/api/admin/novel-projects", json={
        "project_ids": list(ids), "confirmation": confirmation, "confirmation_token": token,
    })


@pytest.mark.asyncio
async def test_batch_deletes_confirmed_set_across_owners_and_preserves_other_projects(db_session):
    await seed(db_session)
    system = await db_session.get(NovelProject, "system-book")
    system.user_id = 1
    for project_id in ["test-book", "system-book"]:
        db_session.add(NovelBlueprint(project_id=project_id, title="蓝图"))
        db_session.add(ChapterOutline(project_id=project_id, chapter_number=1, title="首章"))
        chapter = Chapter(project_id=project_id, chapter_number=1)
        db_session.add(chapter)
        await db_session.flush()
        version = ChapterVersion(chapter_id=chapter.id, content="正文")
        db_session.add(version)
        await db_session.flush()
        chapter.selected_version_id = version.id
    await db_session.commit()
    async with client_for(db_session, {"user": ADMIN}) as client:
        ticket = (await batch_first(client)).json()
        assert await db_session.scalar(select(func.count(NovelProject.id))) == 4
        # The exact set is bound; order changes do not alter the set.
        assert (await batch_final(client, ticket["confirmation_token"], ["system-book", "test-book"])).status_code == 204
    assert set((await db_session.execute(select(NovelProject.id))).scalars()) == {"user-book", "unknown-book"}
    for model in [Chapter, ChapterVersion, ChapterOutline, NovelBlueprint]:
        assert await db_session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("ids,status_code", [
    (["test-book", "user-book"], 403),
    (["system-book", "unknown-book"], 403),
    (["test-book", "missing"], 404),
])
async def test_batch_with_protected_or_missing_project_rejects_entire_set(db_session, ids, status_code):
    await seed(db_session)
    async with client_for(db_session, {"user": ADMIN}) as client:
        assert (await batch_first(client, ids)).status_code == status_code
        token = (await batch_first(client)).json()["confirmation_token"]
        assert (await batch_final(client, token, ids)).status_code == status_code
    assert await db_session.scalar(select(func.count(NovelProject.id))) == 4


@pytest.mark.asyncio
async def test_batch_ticket_cannot_be_reused_for_subset_other_admin_or_single_delete(db_session):
    await seed(db_session)
    holder = {"user": ADMIN}
    async with client_for(db_session, holder) as client:
        token = (await batch_first(client)).json()["confirmation_token"]
        assert (await batch_final(client, token, ["test-book"])).status_code == 403
        assert (await final(client, token)).status_code == 403
        single_ticket = (await first(client)).json()["confirmation_token"]
        assert (await batch_final(client, single_ticket)).status_code == 403
        holder["user"] = ADMIN.model_copy(update={"id": 100})
        assert (await batch_final(client, token)).status_code == 403
        holder["user"] = ADMIN.model_copy(update={"is_admin": False})
        assert (await batch_first(client)).status_code == 403
        assert (await batch_final(client, token)).status_code == 403
    assert await db_session.scalar(select(func.count(NovelProject.id))) == 4


@pytest.mark.asyncio
async def test_batch_input_limits_expiry_and_changed_provenance(db_session):
    await seed(db_session)
    async with client_for(db_session, {"user": ADMIN}) as client:
        for ids in [[], ["test-book", "test-book"], [""], [" test-book"], ["x" * 37], [str(i) for i in range(101)]]:
            assert (await batch_first(client, ids)).status_code == 422
        assert (await batch_first(client, confirmation="确认")).status_code == 422
        token = (await batch_first(client)).json()["confirmation_token"]
        assert (await batch_final(client, token, confirmation="确认")).status_code == 422
        assert (await batch_final(client, "forged")).status_code == 403
        claims = jwt.get_unverified_claims(token)
        claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=5)
        expired = jwt.encode(claims, _confirmation_key(), algorithm=settings.jwt_algorithm)
        assert (await batch_final(client, expired)).status_code == 403
        project = await db_session.get(NovelProject, "system-book")
        project.user_id = 1
        await db_session.commit()
        assert (await batch_final(client, token)).status_code == 403
        token = (await batch_first(client)).json()["confirmation_token"]
        project.creation_source = "user"
        await db_session.commit()
        assert (await batch_final(client, token)).status_code == 403
    assert await db_session.scalar(select(func.count(NovelProject.id))) == 4


@pytest.mark.asyncio
async def test_batch_database_failure_rolls_back_all_projects_and_skips_cleanup(db_session, monkeypatch):
    from app.repositories.novel_repository import NovelRepository
    from app.services.admin_novel_deletion_service import AdminNovelDeletionService

    await seed(db_session)
    service = AdminNovelDeletionService(db_session)
    ticket = await service.confirm_many(["test-book", "system-book"], ADMIN.id, "删除")
    original_delete = NovelRepository.delete
    calls = []

    async def fail_second_delete(repo, project):
        calls.append(project.id)
        if len(calls) == 2:
            raise RuntimeError("simulated database failure")
        await original_delete(repo, project)
        await repo.session.flush()

    cleanup = AsyncMock()
    monkeypatch.setattr(NovelRepository, "delete", fail_second_delete)
    monkeypatch.setattr(CacheService, "invalidate_project_cascade", cleanup)
    with pytest.raises(RuntimeError, match="simulated database failure"):
        await service.delete_many(["test-book", "system-book"], ADMIN.id, "删除", ticket.confirmation_token)
    assert await db_session.scalar(select(func.count(NovelProject.id))) == 4
    cleanup.assert_not_called()
