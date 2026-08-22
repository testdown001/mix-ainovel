"""首页小说摘要统计回归测试。"""

import pytest

from app.models.novel import Chapter, ChapterOutline, ChapterVersion, NovelBlueprint, NovelProject
from app.models.user import User
from app.services.novel_service import NovelService


@pytest.mark.asyncio
async def test_project_summary_returns_real_words_and_next_chapter(db_session):
    user = User(
        id=1201,
        username="home-summary-user",
        email="home-summary@example.com",
        hashed_password="test-hash",
    )
    project = NovelProject(
        id="home-summary-project",
        user_id=user.id,
        title="首页摘要测试",
        initial_prompt="测试首页真实统计",
    )
    blueprint = NovelBlueprint(
        project_id=project.id,
        title=project.title,
        genre="玄幻",
    )
    outlines = [
        ChapterOutline(
            project_id=project.id,
            chapter_number=1,
            title="第一章",
            summary="开端",
        ),
        ChapterOutline(
            project_id=project.id,
            chapter_number=2,
            title="破局前夜",
            summary="承接",
        ),
    ]
    db_session.add_all([user, project, blueprint, *outlines])
    await db_session.flush()

    chapter = Chapter(
        project_id=project.id,
        chapter_number=1,
        status="successful",
        word_count=0,
    )
    db_session.add(chapter)
    await db_session.flush()

    selected_content = "这一段正文用于验证旧章节缺少字数缓存时仍能正确统计。"
    version = ChapterVersion(
        chapter_id=chapter.id,
        version_label="最终稿",
        content=selected_content,
    )
    db_session.add(version)
    await db_session.flush()
    chapter.selected_version_id = version.id
    await db_session.commit()

    summaries = await NovelService(db_session).list_projects_for_user(user.id)

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.completed_chapters == 1
    assert summary.total_chapters == 2
    assert summary.total_words == len(selected_content)
    assert summary.next_chapter_number == 2
    assert summary.next_chapter_title == "破局前夜"
