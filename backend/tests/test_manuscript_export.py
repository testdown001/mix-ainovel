"""全书导出白名单 + 预检只提示不拦截 + ai_assisted 落库。"""
import io
import zipfile

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.models.user_quota  # noqa: F401
from app.api.routers import novels
from app.core.dependencies import get_current_user
from app.db.session import get_session
from app.models.novel import Chapter, ChapterOutline, ChapterVersion, NovelBlueprint, NovelProject
from app.models.user import User
from app.schemas.user import UserInDB
from app.services.compliance_precheck_service import scan_text
from app.services.novel_service import NovelService

OWNER = UserInDB(id=31, username="exporter", hashed_password="x")
INTRUDER = UserInDB(id=32, username="nosy", hashed_password="x")
PROJECT_ID = "proj-export-1"


def _build_client(db_session, user_holder):
    test_app = FastAPI()
    test_app.include_router(novels.router)

    async def _override_session():
        yield db_session

    async def _override_user():
        return user_holder["user"]

    test_app.dependency_overrides[get_session] = _override_session
    test_app.dependency_overrides[get_current_user] = _override_user
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


async def _seed(db_session):
    db_session.add_all(
        [
            User(id=OWNER.id, username=OWNER.username, email="ex@example.com", hashed_password="x"),
            User(id=INTRUDER.id, username=INTRUDER.username, email="no@example.com", hashed_password="x"),
            NovelProject(id=PROJECT_ID, user_id=OWNER.id, title="导出测试", ai_assisted=True),
            NovelBlueprint(project_id=PROJECT_ID, one_sentence_summary="简介"),
        ]
    )
    for num, title in ((1, "开篇"), (2, "未完"), (3, "高潮")):
        db_session.add(ChapterOutline(project_id=PROJECT_ID, chapter_number=num, title=title))
    ch1 = Chapter(project_id=PROJECT_ID, chapter_number=1, status="successful", word_count=12)
    ch2 = Chapter(project_id=PROJECT_ID, chapter_number=2, status="generating", word_count=0)
    ch3 = Chapter(project_id=PROJECT_ID, chapter_number=3, status="successful", word_count=12)
    db_session.add_all([ch1, ch2, ch3])
    await db_session.flush()
    v1 = ChapterVersion(chapter_id=ch1.id, content="第一章正文。详细血腥描写在此。", ai_assisted=True)
    v3 = ChapterVersion(chapter_id=ch3.id, content="第三章正文内容。", ai_assisted=False)
    db_session.add_all([v1, v3])
    await db_session.flush()
    ch1.selected_version_id = v1.id
    ch3.selected_version_id = v3.id
    await db_session.commit()


@pytest.mark.asyncio
async def test_export_txt_only_finalized_chapters(db_session):
    await _seed(db_session)
    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        resp = await client.get(f"/api/novels/{PROJECT_ID}/export?format=txt")
    assert resp.status_code == 200
    body = resp.text
    assert "第一章正文" in body
    assert "第三章正文" in body
    assert "未完" not in body
    assert "含 AI 辅助" in body
    assert "attachment" in resp.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_export_docx_is_ooxml_zip(db_session):
    await _seed(db_session)
    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        resp = await client.get(f"/api/novels/{PROJECT_ID}/export?format=docx")
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = set(zf.namelist())
        assert "[Content_Types].xml" in names
        assert "word/document.xml" in names
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "第一章正文" in xml
    assert "第三章正文" in xml
    assert "未完" not in xml


@pytest.mark.asyncio
async def test_export_rejects_non_owner(db_session):
    await _seed(db_session)
    holder = {"user": INTRUDER}
    async with _build_client(db_session, holder) as client:
        resp = await client.get(f"/api/novels/{PROJECT_ID}/export?format=txt")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_precheck_is_advisory_never_blocks(db_session):
    await _seed(db_session)
    holder = {"user": OWNER}
    async with _build_client(db_session, holder) as client:
        resp = await client.post(
            f"/api/novels/{PROJECT_ID}/compliance/precheck",
            json={"platform": "qidian"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["blocked"] is False
    assert data["advisory"] is True
    assert data["hit_count"] >= 1
    assert any(hit["term"] == "详细血腥描写" for hit in data["hits"])


@pytest.mark.asyncio
async def test_scan_text_is_pure_advisory():
    hits = scan_text("这里有详细血腥描写和别的", ["详细血腥描写"])
    assert hits[0]["term"] == "详细血腥描写"
    assert "建议" in hits[0]["hint"]


@pytest.mark.asyncio
async def test_replace_versions_sets_ai_assisted(db_session):
    db_session.add_all(
        [
            User(id=OWNER.id, username=OWNER.username, email="ex@example.com", hashed_password="x"),
            NovelProject(id=PROJECT_ID, user_id=OWNER.id, title="旗标", ai_assisted=False),
        ]
    )
    chapter = Chapter(project_id=PROJECT_ID, chapter_number=1, status="not_generated")
    db_session.add(chapter)
    await db_session.commit()
    await db_session.refresh(chapter)

    svc = NovelService(db_session)
    versions = await svc.replace_chapter_versions(chapter, ["模型起草的正文一段。"])
    assert versions[0].ai_assisted is True
    project = await db_session.get(NovelProject, PROJECT_ID)
    assert project.ai_assisted is True
