"""novels 路由所有权校验 + 蓝图重生成保护回归测试。

覆盖两组修复：
1. scenes / concepts 共 7 个端点的项目归属校验（非属主 403、项目不存在 404、属主不受影响）；
2. POST /{project_id}/blueprint/generate 的重生成保护（已定稿章节或大纲已扩写 → 409 且不调 LLM）。

通过最小 FastAPI 应用挂载真实 novels 路由 + dependency_overrides，
底层走 conftest 的真内存 SQLite 会话，真正命中被修路径。
"""
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.models.user_quota  # noqa: F401  触发 mapper 注册，防 KeyError
from app.api.routers import novels
from app.core.dependencies import get_current_user
from app.db.session import get_session
from app.models.entity_registry import EntityRegistry
from app.models.novel import Chapter, ChapterOutline, NovelProject
from app.schemas.user import UserInDB

OWNER = UserInDB(id=1, username="owner", hashed_password="x")
INTRUDER = UserInDB(id=2, username="intruder", hashed_password="x")

PROJECT_ID = "proj-owner-1"


def _build_client(db_session, user_holder):
    """挂载真实 novels 路由的最小应用，get_session/get_current_user 用测试替身。"""
    test_app = FastAPI()
    test_app.include_router(novels.router)

    async def _override_session():
        yield db_session

    async def _override_user():
        return user_holder["user"]

    test_app.dependency_overrides[get_session] = _override_session
    test_app.dependency_overrides[get_current_user] = _override_user
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


def _patch_llm(monkeypatch, response_text='{"scenes": []}'):
    """替换 novels 模块内的 LLMService，记录调用并返回固定文本。"""
    calls = []

    class _FakeLLMService:
        def __init__(self, session):
            pass

        async def get_llm_response(self, **kwargs):
            calls.append(kwargs)
            return response_text

    monkeypatch.setattr(novels, "LLMService", _FakeLLMService)
    return calls


async def _seed_project(db_session, *, with_outline=True, with_concept=True):
    db_session.add(NovelProject(id=PROJECT_ID, user_id=OWNER.id, title="属主的项目"))
    if with_outline:
        db_session.add(
            ChapterOutline(
                project_id=PROJECT_ID,
                chapter_number=1,
                title="第一章",
                summary="开篇",
                metadata_={"scenes": [{"title": "原场景", "summary": "", "location": "", "characters": [], "mood": ""}]},
            )
        )
    concept_id = None
    if with_concept:
        entity = EntityRegistry(
            project_id=PROJECT_ID,
            entity_type="character",
            canonical_name="张三",
            description="主角",
            source="manual",
            confidence=1.0,
            properties={},
        )
        db_session.add(entity)
        await db_session.flush()
        concept_id = entity.id
    await db_session.commit()
    return concept_id


# ------------------------------------------------------------------
# 0.1 场景端点归属校验
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenes_get_rejects_non_owner(db_session):
    await _seed_project(db_session)
    holder = {"user": INTRUDER}
    async with _build_client(db_session, holder) as client:
        resp = await client.get(f"/api/novels/{PROJECT_ID}/outlines/1/scenes")
        assert resp.status_code == 403

        # 属主访问不受影响
        holder["user"] = OWNER
        resp = await client.get(f"/api/novels/{PROJECT_ID}/outlines/1/scenes")
        assert resp.status_code == 200
        assert resp.json()["scenes"][0]["title"] == "原场景"


@pytest.mark.asyncio
async def test_scenes_get_missing_project_returns_404(db_session):
    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        resp = await client.get("/api/novels/no-such-project/outlines/1/scenes")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_scenes_put_rejects_non_owner_and_keeps_data(db_session):
    await _seed_project(db_session)
    holder = {"user": INTRUDER}
    payload = {"scenes": [{"title": "篡改场景"}]}
    async with _build_client(db_session, holder) as client:
        resp = await client.put(f"/api/novels/{PROJECT_ID}/outlines/1/scenes", json=payload)
        assert resp.status_code == 403

        # 数据未被篡改，且属主可正常写入
        holder["user"] = OWNER
        resp = await client.get(f"/api/novels/{PROJECT_ID}/outlines/1/scenes")
        assert resp.json()["scenes"][0]["title"] == "原场景"

        resp = await client.put(f"/api/novels/{PROJECT_ID}/outlines/1/scenes", json=payload)
        assert resp.status_code == 200
        assert resp.json()["scenes"][0]["title"] == "篡改场景"


@pytest.mark.asyncio
async def test_scenes_generate_rejects_non_owner_without_llm_call(db_session, monkeypatch):
    calls = _patch_llm(monkeypatch)
    await _seed_project(db_session)
    holder = {"user": INTRUDER}
    async with _build_client(db_session, holder) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/outlines/1/scenes/generate")
        assert resp.status_code == 403
        assert calls == []

        # 属主走正常生成路径
        holder["user"] = OWNER
        _patch_llm(monkeypatch, '{"scenes": [{"title": "新场景", "summary": "s", "location": "l", "characters": [], "mood": "紧张"}]}')
        resp = await client.post(f"/api/novels/{PROJECT_ID}/outlines/1/scenes/generate")
        assert resp.status_code == 200
        assert resp.json()["scenes"][0]["title"] == "新场景"


# ------------------------------------------------------------------
# 0.1 概念端点归属校验
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concepts_list_rejects_non_owner(db_session):
    await _seed_project(db_session)
    holder = {"user": INTRUDER}
    async with _build_client(db_session, holder) as client:
        resp = await client.get(f"/api/novels/{PROJECT_ID}/concepts")
        assert resp.status_code == 403

        holder["user"] = OWNER
        resp = await client.get(f"/api/novels/{PROJECT_ID}/concepts")
        assert resp.status_code == 200
        assert [c["canonical_name"] for c in resp.json()] == ["张三"]


@pytest.mark.asyncio
async def test_concepts_create_rejects_non_owner(db_session):
    await _seed_project(db_session, with_concept=False)
    holder = {"user": INTRUDER}
    payload = {"entity_type": "location", "canonical_name": "黑森林"}
    async with _build_client(db_session, holder) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/concepts", json=payload)
        assert resp.status_code == 403

        holder["user"] = OWNER
        resp = await client.get(f"/api/novels/{PROJECT_ID}/concepts")
        assert resp.json() == []  # 非属主的创建未落库

        resp = await client.post(f"/api/novels/{PROJECT_ID}/concepts", json=payload)
        assert resp.status_code == 200
        assert resp.json()["message"] == "概念创建成功"


@pytest.mark.asyncio
async def test_concepts_update_rejects_non_owner(db_session):
    concept_id = await _seed_project(db_session)
    holder = {"user": INTRUDER}
    payload = {"canonical_name": "李四"}
    async with _build_client(db_session, holder) as client:
        resp = await client.put(f"/api/novels/{PROJECT_ID}/concepts/{concept_id}", json=payload)
        assert resp.status_code == 403

        holder["user"] = OWNER
        resp = await client.get(f"/api/novels/{PROJECT_ID}/concepts")
        assert resp.json()[0]["canonical_name"] == "张三"  # 未被篡改

        resp = await client.put(f"/api/novels/{PROJECT_ID}/concepts/{concept_id}", json=payload)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_concepts_delete_rejects_non_owner(db_session):
    concept_id = await _seed_project(db_session)
    holder = {"user": INTRUDER}
    async with _build_client(db_session, holder) as client:
        resp = await client.delete(f"/api/novels/{PROJECT_ID}/concepts/{concept_id}")
        assert resp.status_code == 403

        holder["user"] = OWNER
        resp = await client.get(f"/api/novels/{PROJECT_ID}/concepts")
        assert len(resp.json()) == 1  # 未被删除

        resp = await client.delete(f"/api/novels/{PROJECT_ID}/concepts/{concept_id}")
        assert resp.status_code == 200


# ------------------------------------------------------------------
# 0.3 蓝图重生成保护
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_blueprint_regen_blocked_by_finalized_chapter(db_session, monkeypatch):
    calls = _patch_llm(monkeypatch)
    await _seed_project(db_session, with_concept=False)
    db_session.add(
        Chapter(project_id=PROJECT_ID, chapter_number=1, status="completed", selected_version_id=999)
    )
    await db_session.commit()

    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")
        assert resp.status_code == 409
        assert "章节创作成果" in resp.json()["detail"]
        assert calls == []  # 拒绝发生在 LLM 调用之前


@pytest.mark.asyncio
async def test_blueprint_regen_blocked_by_draft_versions(db_session, monkeypatch):
    """未定稿但已有草稿版本，同样视为创作成果，拒绝重生成。"""
    from app.models.novel import ChapterVersion

    calls = _patch_llm(monkeypatch)
    await _seed_project(db_session, with_concept=False)
    chapter = Chapter(project_id=PROJECT_ID, chapter_number=1, status="waiting_for_confirm")
    db_session.add(chapter)
    await db_session.flush()
    db_session.add(ChapterVersion(chapter_id=chapter.id, content="草稿正文"))
    await db_session.commit()

    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")
        assert resp.status_code == 409
        assert calls == []


@pytest.mark.asyncio
async def test_blueprint_regen_allowed_with_expanded_outline_only(db_session, monkeypatch):
    """纯大纲扩写、零章节写作：允许重生成（走原有流程，无对话历史 → 400）。"""
    _patch_llm(monkeypatch)
    db_session.add(NovelProject(id=PROJECT_ID, user_id=OWNER.id, title="扩写项目"))
    for n in range(1, 52):
        db_session.add(ChapterOutline(project_id=PROJECT_ID, chapter_number=n, title=f"第{n}章"))
    await db_session.commit()

    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")
        assert resp.status_code == 400
        assert "缺少对话历史" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_blueprint_generate_untouched_for_fresh_project(db_session, monkeypatch):
    """空项目（无定稿章、大纲未扩写）不触发 409，仍走原有流程（无对话历史 → 400）。"""
    _patch_llm(monkeypatch)
    await _seed_project(db_session, with_concept=False)

    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")
        assert resp.status_code == 400
        assert "缺少对话历史" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_blueprint_generate_rejects_non_owner(db_session, monkeypatch):
    calls = _patch_llm(monkeypatch)
    await _seed_project(db_session, with_concept=False)
    holder = {"user": INTRUDER}
    async with _build_client(db_session, holder) as client:
        resp = await client.post(f"/api/novels/{PROJECT_ID}/blueprint/generate")
        assert resp.status_code == 403
        assert calls == []
