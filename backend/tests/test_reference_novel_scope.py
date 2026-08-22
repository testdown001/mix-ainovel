from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.models.user_quota  # noqa: F401  触发 mapper 注册
from app.api.routers import reference_novels
from app.core.dependencies import get_current_user
from app.db.session import get_session
from app.models.novel import NovelProject
from app.models.reference_novel import ReferenceNovel
from app.schemas.user import UserInDB


OWNER = UserInDB(id=1, username="owner", hashed_password="x")
INTRUDER = UserInDB(id=2, username="intruder", hashed_password="x")


def _build_client(db_session, user_holder):
    test_app = FastAPI()
    test_app.include_router(reference_novels.router)

    async def _override_session():
        yield db_session

    async def _override_user():
        return user_holder["user"]

    test_app.dependency_overrides[get_session] = _override_session
    test_app.dependency_overrides[get_current_user] = _override_user
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


async def _seed_scoped_references(db_session):
    now = datetime.now(timezone.utc)
    current_first = ReferenceNovel(
        title="重生97，我在市局破悬案",
        user_id=OWNER.id,
        status="ready",
        created_at=now,
        updated_at=now,
    )
    current_second = ReferenceNovel(
        title="大医凌然",
        user_id=OWNER.id,
        status="ready",
        created_at=now,
        updated_at=now,
    )
    another_project = ReferenceNovel(
        title="神秘复苏",
        user_id=OWNER.id,
        status="ready",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([current_first, current_second, another_project])
    await db_session.flush()
    db_session.add_all([
        NovelProject(
            id="current-project",
            user_id=OWNER.id,
            title="当前小说",
            reference_novel_ids=[current_first.id, current_second.id],
        ),
        NovelProject(
            id="another-project",
            user_id=OWNER.id,
            title="另一部小说",
            reference_novel_ids=[another_project.id],
        ),
    ])
    await db_session.commit()
    return current_first, current_second, another_project


@pytest.mark.asyncio
async def test_library_without_current_novel_scope_returns_empty(db_session):
    await _seed_scoped_references(db_session)
    holder = {"user": OWNER}

    async with _build_client(db_session, holder) as client:
        response = await client.get("/api/reference-novels")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_project_library_only_returns_that_projects_references(db_session):
    _, _, another_project = await _seed_scoped_references(db_session)
    holder = {"user": OWNER}

    async with _build_client(db_session, holder) as client:
        response = await client.get(
            "/api/reference-novels",
            params={"project_id": "current-project"},
        )

    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == [
        "重生97，我在市局破悬案",
        "大医凌然",
    ]
    assert another_project.id not in [item["id"] for item in response.json()]


@pytest.mark.asyncio
async def test_draft_library_only_returns_explicitly_selected_ids(db_session):
    current_first, _, another_project = await _seed_scoped_references(db_session)
    holder = {"user": OWNER}

    async with _build_client(db_session, holder) as client:
        response = await client.get(
            "/api/reference-novels",
            params=[("ids", str(current_first.id)), ("ids", str(another_project.id))],
        )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [current_first.id, another_project.id]


@pytest.mark.asyncio
async def test_project_library_rejects_non_owner(db_session):
    await _seed_scoped_references(db_session)
    holder = {"user": INTRUDER}

    async with _build_client(db_session, holder) as client:
        response = await client.get(
            "/api/reference-novels",
            params={"project_id": "current-project"},
        )

    assert response.status_code == 403
