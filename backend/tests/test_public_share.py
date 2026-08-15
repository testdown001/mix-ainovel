"""作品公开分享的回归测试。

覆盖安全红线与核心契约：
- 开启幂等（两次 POST 同 token）、关闭后旧链接 404、无效 token 404；
- 公开目录只列已完稿章节（successful + selected_version），generating 不出现；
- 正文端点返回 selected_version 内容与相邻已完稿章号（prev/next 跳过未完稿）；
- 响应字段是显式白名单——绝不含 email/user_id/积分/蓝图设定/版本列表；
- owner 端点非属主 404（不泄露项目存在性，口径同 writer_progress 三兄弟）。
"""
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.models.user_quota  # noqa: F401  触发 mapper 注册
from app.api.routers import novels, public_share
from app.core.dependencies import get_current_user
from app.db.session import get_session
from app.models.novel import Chapter, ChapterOutline, ChapterVersion, NovelBlueprint, NovelProject
from app.models.user import User
from app.schemas.user import UserInDB
from app.services import referral_service

OWNER = UserInDB(id=1, username="author", hashed_password="x")
INTRUDER = UserInDB(id=2, username="intruder", hashed_password="x")
PROJECT_ID = "proj-share-1"


def _build_client(db_session, user_holder):
    test_app = FastAPI()
    test_app.include_router(novels.router)
    test_app.include_router(public_share.router)

    async def _override_session():
        yield db_session

    async def _override_user():
        return user_holder["user"]

    test_app.dependency_overrides[get_session] = _override_session
    test_app.dependency_overrides[get_current_user] = _override_user
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


async def _seed(db_session):
    """1/3 章已完稿（successful + selected_version），2 章 generating 无版本。"""
    db_session.add_all(
        [
            User(id=OWNER.id, username=OWNER.username, email="author@example.com", hashed_password="x"),
            User(id=INTRUDER.id, username=INTRUDER.username, hashed_password="x"),
            NovelProject(id=PROJECT_ID, user_id=OWNER.id, title="测试小说"),
            NovelBlueprint(project_id=PROJECT_ID, one_sentence_summary="一句话简介"),
        ]
    )
    for num, title in ((1, "初入宗门"), (2, "炼气一层"), (3, "筑基大典")):
        db_session.add(ChapterOutline(project_id=PROJECT_ID, chapter_number=num, title=title))
    ch1 = Chapter(project_id=PROJECT_ID, chapter_number=1, status="successful", word_count=1000)
    ch2 = Chapter(project_id=PROJECT_ID, chapter_number=2, status="generating", word_count=0)
    ch3 = Chapter(project_id=PROJECT_ID, chapter_number=3, status="successful", word_count=2000)
    db_session.add_all([ch1, ch2, ch3])
    await db_session.flush()
    v1 = ChapterVersion(chapter_id=ch1.id, content="第一章正文内容")
    v3 = ChapterVersion(chapter_id=ch3.id, content="第三章正文内容")
    db_session.add_all([v1, v3])
    await db_session.flush()
    ch1.selected_version_id = v1.id
    ch3.selected_version_id = v3.id
    await db_session.commit()


async def _enable(client) -> str:
    resp = await client.post(f"/api/novels/{PROJECT_ID}/share")
    assert resp.status_code == 200
    return resp.json()["share_token"]


@pytest.mark.asyncio
async def test_enable_share_is_idempotent(db_session):
    await _seed(db_session)
    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        first = await client.post(f"/api/novels/{PROJECT_ID}/share")
        second = await client.post(f"/api/novels/{PROJECT_ID}/share")
        assert first.status_code == second.status_code == 200
        assert first.json()["share_token"] == second.json()["share_token"]
        token = first.json()["share_token"]
        assert first.json()["share_url_path"] == f"/share/{token}"

        status_resp = await client.get(f"/api/novels/{PROJECT_ID}/share")
        assert status_resp.json() == {"enabled": True, "share_token": token}


@pytest.mark.asyncio
async def test_public_overview_lists_only_completed_chapters(db_session):
    await _seed(db_session)
    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        token = await _enable(client)
        resp = await client.get(f"/api/public/shared/{token}")

    assert resp.status_code == 200
    data = resp.json()
    # 显式白名单：不含 email/user_id/积分/蓝图设定/版本列表
    assert set(data.keys()) == {
        "title", "description", "author_name", "chapter_count", "chapters",
        "author_invite_code", "ai_assisted",
    }
    assert data["title"] == "测试小说"
    assert data["description"] == "一句话简介"
    assert data["author_name"] == "author"
    assert data["author_invite_code"] == referral_service.build_invite_code(OWNER.id)
    # generating 的第 2 章绝不出现
    assert data["chapter_count"] == 2
    assert [c["chapter_number"] for c in data["chapters"]] == [1, 3]
    assert data["chapters"][0] == {"chapter_number": 1, "title": "初入宗门", "word_count": 1000}
    for chapter in data["chapters"]:
        assert set(chapter.keys()) == {"chapter_number", "title", "word_count"}
    assert "email" not in resp.text
    assert "author@example.com" not in resp.text


@pytest.mark.asyncio
async def test_public_chapter_content_and_neighbors(db_session):
    await _seed(db_session)
    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        token = await _enable(client)
        ch1 = await client.get(f"/api/public/shared/{token}/chapters/1")
        ch3 = await client.get(f"/api/public/shared/{token}/chapters/3")
        ch2 = await client.get(f"/api/public/shared/{token}/chapters/2")

    assert ch1.status_code == 200
    data1 = ch1.json()
    assert set(data1.keys()) == {"chapter_number", "title", "content", "prev", "next", "ai_assisted"}
    assert data1["content"] == "第一章正文内容"
    assert data1["title"] == "初入宗门"
    # prev/next 跳过未完稿的第 2 章
    assert data1["prev"] is None
    assert data1["next"] == 3

    data3 = ch3.json()
    assert data3["content"] == "第三章正文内容"
    assert data3["prev"] == 1
    assert data3["next"] is None

    # 未完稿章节与无效 token 同语义
    assert ch2.status_code == 404


@pytest.mark.asyncio
async def test_invalid_token_is_404(db_session):
    await _seed(db_session)
    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        overview = await client.get("/api/public/shared/no-such-token")
        chapter = await client.get("/api/public/shared/no-such-token/chapters/1")
    assert overview.status_code == 404
    assert chapter.status_code == 404


@pytest.mark.asyncio
async def test_disable_share_invalidates_old_link(db_session):
    await _seed(db_session)
    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        token = await _enable(client)
        assert (await client.get(f"/api/public/shared/{token}")).status_code == 200

        disable = await client.delete(f"/api/novels/{PROJECT_ID}/share")
        assert disable.status_code == 204

        assert (await client.get(f"/api/public/shared/{token}")).status_code == 404
        assert (await client.get(f"/api/public/shared/{token}/chapters/1")).status_code == 404
        status_resp = await client.get(f"/api/novels/{PROJECT_ID}/share")
        assert status_resp.json() == {"enabled": False, "share_token": None}

        # 重新开启生成的新 token 与旧的不同（旧链接作废语义）
        new_token = await _enable(client)
        assert new_token != token


@pytest.mark.asyncio
async def test_owner_endpoints_reject_non_owner_with_404(db_session):
    await _seed(db_session)
    holder = {"user": INTRUDER}
    async with _build_client(db_session, holder) as client:
        get_resp = await client.get(f"/api/novels/{PROJECT_ID}/share")
        post_resp = await client.post(f"/api/novels/{PROJECT_ID}/share")
        delete_resp = await client.delete(f"/api/novels/{PROJECT_ID}/share")
    assert get_resp.status_code == 404
    assert post_resp.status_code == 404
    assert delete_resp.status_code == 404
