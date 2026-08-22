"""M2：章节本地草稿协同的服务端保存契约。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.error_codes import DomainErrorCode
from app.models.novel import Chapter, ChapterVersion, NovelProject
from app.models.user import User
from app.services.chapter_revision_service import ChapterRevisionService, hash_chapter_content


async def _seed_chapter(db_session):
    user = User(
        id=7201,
        username="m2-writer",
        email="m2-writer@example.com",
        hashed_password="test-hash",
    )
    project = NovelProject(
        id="m2-reliable-save-project",
        user_id=user.id,
        title="可靠保存测试",
        initial_prompt="M2",
    )
    db_session.add_all([user, project])
    await db_session.flush()

    chapter = Chapter(project_id=project.id, chapter_number=1, status="successful")
    db_session.add(chapter)
    await db_session.flush()
    original = ChapterVersion(chapter_id=chapter.id, content="原始正文", version_label="v1")
    db_session.add(original)
    await db_session.flush()
    chapter.selected_version_id = original.id
    chapter.revision_id = 0
    chapter.content_hash = hash_chapter_content(original.content)
    await db_session.commit()
    return project, chapter, original


@pytest.mark.asyncio
async def test_manual_save_creates_new_version_and_advances_revision(db_session):
    project, chapter, original = await _seed_chapter(db_session)
    service = ChapterRevisionService(db_session)
    baseline = await service.get_revision(project.id, 1)

    saved = await service.save(
        project_id=project.id,
        chapter_number=1,
        content="作者修订后的正文",
        expected_revision_id=baseline.revision_id,
        expected_content_hash=baseline.content_hash,
    )

    await db_session.refresh(chapter)
    assert saved.status == "saved"
    assert chapter.revision_id == 1
    assert chapter.selected_version_id == saved.saved_version_id
    assert original.content == "原始正文"  # 历史文本不能被手工保存原地改写。
    versions = (await db_session.execute(
        select(ChapterVersion).where(ChapterVersion.chapter_id == chapter.id)
    )).scalars().all()
    assert [version.content for version in versions] == ["原始正文", "作者修订后的正文"]


@pytest.mark.asyncio
async def test_stale_baseline_is_rejected_without_creating_extra_version(db_session):
    project, chapter, _ = await _seed_chapter(db_session)
    service = ChapterRevisionService(db_session)
    baseline = await service.get_revision(project.id, 1)
    await service.save(
        project_id=project.id,
        chapter_number=1,
        content="另一台设备已保存",
        expected_revision_id=baseline.revision_id,
        expected_content_hash=baseline.content_hash,
    )

    with pytest.raises(Exception) as exc_info:
        await service.save(
            project_id=project.id,
            chapter_number=1,
            content="过期页面尝试覆盖",
            expected_revision_id=baseline.revision_id,
            expected_content_hash=baseline.content_hash,
        )

    assert getattr(exc_info.value, "status_code", None) == 409
    assert exc_info.value.detail["code"] == DomainErrorCode.VERSION_CONFLICT
    versions = (await db_session.execute(
        select(ChapterVersion).where(ChapterVersion.chapter_id == chapter.id)
    )).scalars().all()
    assert len(versions) == 2


@pytest.mark.asyncio
async def test_lost_response_retry_is_idempotent(db_session):
    project, chapter, _ = await _seed_chapter(db_session)
    service = ChapterRevisionService(db_session)
    baseline = await service.get_revision(project.id, 1)
    first = await service.save(
        project_id=project.id,
        chapter_number=1,
        content="网络超时前已落库的正文",
        expected_revision_id=baseline.revision_id,
        expected_content_hash=baseline.content_hash,
    )

    retry = await service.save(
        project_id=project.id,
        chapter_number=1,
        content="网络超时前已落库的正文",
        expected_revision_id=baseline.revision_id,
        expected_content_hash=baseline.content_hash,
    )

    versions = (await db_session.execute(
        select(ChapterVersion).where(ChapterVersion.chapter_id == chapter.id)
    )).scalars().all()
    assert retry.status == "saved"
    assert retry.saved_version_id == first.saved_version_id
    assert len(versions) == 2


@pytest.mark.asyncio
async def test_conflict_branch_preserves_local_text_without_replacing_selected_version(db_session):
    project, chapter, _ = await _seed_chapter(db_session)
    service = ChapterRevisionService(db_session)
    baseline = await service.get_revision(project.id, 1)
    remote = await service.save(
        project_id=project.id,
        chapter_number=1,
        content="远端新正文",
        expected_revision_id=baseline.revision_id,
        expected_content_hash=baseline.content_hash,
    )

    branched = await service.save(
        project_id=project.id,
        chapter_number=1,
        content="本地冲突草稿",
        expected_revision_id=baseline.revision_id,
        expected_content_hash=baseline.content_hash,
        mode="branch",
    )

    await db_session.refresh(chapter)
    branch = await db_session.get(ChapterVersion, branched.saved_version_id)
    assert branched.status == "branched"
    assert chapter.selected_version_id == remote.saved_version_id
    assert chapter.revision_id == 1
    assert branch and branch.content == "本地冲突草稿"
    assert branch.metadata["m2_edit"]["kind"] == "conflict_branch"
