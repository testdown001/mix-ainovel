"""M3：不可变历史、恢复链、Diff 与内存导出。"""
from __future__ import annotations

import io
import zipfile

import pytest
from sqlalchemy import select

from app.models.novel import Chapter, ChapterOutline, ChapterVersion, NovelProject, Volume
from app.models.user import User
from app.services.chapter_history_service import ChapterHistoryService, build_text_diff
from app.services.chapter_revision_service import ChapterRevisionService, hash_chapter_content
from app.services.manuscript_export_service import (
    assemble_markdown,
    assemble_txt,
    build_docx_bytes,
    collect_export_chapters,
    collect_export_volumes,
)


async def _seed(db_session):
    user = User(id=7301, username="m3-writer", email="m3-writer@example.com", hashed_password="test")
    project = NovelProject(id="m3-history-project", user_id=user.id, title="M3 导出测试", initial_prompt="M3")
    db_session.add_all([user, project])
    await db_session.flush()

    volume = Volume(project_id=project.id, position=1, name="初入仙途", start_chapter=1, end_chapter=10)
    outline = ChapterOutline(project_id=project.id, chapter_number=1, title="风雪登山", summary="测试")
    chapter = Chapter(project_id=project.id, chapter_number=1, status="successful", sort_key=1000)
    db_session.add_all([volume, outline, chapter])
    await db_session.flush()

    original = ChapterVersion(
        chapter_id=chapter.id,
        content="旧日风雪。\n\n少年登山。",
        version_label="legacy_v1",
        source="legacy",
        content_hash=hash_chapter_content("旧日风雪。\n\n少年登山。"),
    )
    db_session.add(original)
    await db_session.flush()
    chapter.selected_version_id = original.id
    chapter.content_hash = original.content_hash
    await db_session.commit()
    return project, chapter, original


@pytest.mark.asyncio
async def test_restore_creates_a_new_snapshot_with_parent_lineage(db_session):
    project, chapter, original = await _seed(db_session)
    revisions = ChapterRevisionService(db_session)
    baseline = await revisions.get_revision(project.id, 1)
    edited = await revisions.save(
        project_id=project.id,
        chapter_number=1,
        content="新章正文。",
        expected_revision_id=baseline.revision_id,
        expected_content_hash=baseline.content_hash,
        actor_user_id=7301,
    )
    baseline = await revisions.get_revision(project.id, 1)

    restored = await ChapterHistoryService(db_session).restore_version(
        project_id=project.id,
        version_id=original.id,
        expected_revision_id=baseline.revision_id,
        expected_content_hash=baseline.content_hash,
        change_note="回到开篇语气",
        actor_user_id=7301,
    )
    restored_version = await db_session.get(ChapterVersion, restored.saved_version_id)
    versions = (
        await db_session.execute(
            select(ChapterVersion).where(ChapterVersion.chapter_id == chapter.id).order_by(ChapterVersion.id)
        )
    ).scalars().all()

    assert len(versions) == 3
    assert original.content == "旧日风雪。\n\n少年登山。"
    assert restored_version is not None
    assert restored_version.content == original.content
    assert restored_version.parent_version_id == original.id
    assert restored_version.source == "history_restore"
    assert restored_version.content_hash == hash_chapter_content(original.content)
    assert edited.saved_version_id != restored.saved_version_id


@pytest.mark.asyncio
async def test_history_list_hides_body_and_diff_marks_changed_text(db_session):
    project, _chapter, original = await _seed(db_session)
    revisions = ChapterRevisionService(db_session)
    baseline = await revisions.get_revision(project.id, 1)
    changed = await revisions.save(
        project_id=project.id,
        chapter_number=1,
        content="旧日春雪。\n\n少年下山。",
        expected_revision_id=baseline.revision_id,
        expected_content_hash=baseline.content_hash,
    )

    history = ChapterHistoryService(db_session)
    listing = await history.list_versions(project.id, 1)
    compared = await history.compare_versions(project.id, original.id, changed.saved_version_id)

    assert listing["total_count"] == 2
    assert listing["total_content_bytes"] > 0
    assert "content" not in listing["items"][0]
    assert listing["items"][0]["content_bytes"] > 0
    assert any(segment["kind"] == "delete" for segment in compared["left_segments"])
    assert any(segment["kind"] == "insert" for segment in compared["right_segments"])
    left, right = build_text_diff("甲乙", "甲丙")
    assert "".join(item["text"] for item in left if item["kind"] == "delete") == "乙"
    assert "".join(item["text"] for item in right if item["kind"] == "insert") == "丙"


@pytest.mark.asyncio
async def test_history_uses_stable_cursor_pagination(db_session):
    project, _chapter, _original = await _seed(db_session)
    revisions = ChapterRevisionService(db_session)
    for content in ("第二版", "第三版", "第四版"):
        baseline = await revisions.get_revision(project.id, 1)
        await revisions.save(
            project_id=project.id,
            chapter_number=1,
            content=content,
            expected_revision_id=baseline.revision_id,
            expected_content_hash=baseline.content_hash,
        )

    history = ChapterHistoryService(db_session)
    first = await history.list_versions(project.id, 1, limit=2)
    second = await history.list_versions(
        project.id,
        1,
        limit=2,
        before_id=first["next_before_id"],
    )

    assert first["total_count"] == 4
    assert first["has_more"] is True
    assert second["has_more"] is False
    assert {item["id"] for item in first["items"]}.isdisjoint(
        {item["id"] for item in second["items"]}
    )


@pytest.mark.asyncio
async def test_structured_exports_keep_volume_chapter_and_docx_in_memory(db_session):
    project, _chapter, _original = await _seed(db_session)
    chapters = await collect_export_chapters(db_session, project)
    volumes = await collect_export_volumes(db_session, project, chapters)
    markdown = assemble_markdown(project, chapters, volumes)
    txt = assemble_txt(project, chapters, volumes)
    docx = build_docx_bytes(project, chapters, volumes)

    assert "## 第1卷 初入仙途" in markdown
    assert "### 第1章 风雪登山" in markdown
    assert "　　旧日风雪。" in txt
    assert docx.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(docx)) as package:
        document = package.read("word/document.xml").decode("utf-8")
    assert "第1卷 初入仙途" in document
    assert "风雪登山" in document


@pytest.mark.asyncio
async def test_export_keeps_confirmed_text_while_new_candidates_wait_for_selection(db_session):
    project, chapter, original = await _seed(db_session)
    chapter.status = "waiting_for_confirm"
    db_session.add(
        ChapterVersion(
            chapter_id=chapter.id,
            content="尚未采纳的新候选。",
            version_label="generation_pending",
            source="generation",
        )
    )
    await db_session.commit()

    chapters = await collect_export_chapters(db_session, project)

    assert len(chapters) == 1
    assert chapters[0][2] == original.content
