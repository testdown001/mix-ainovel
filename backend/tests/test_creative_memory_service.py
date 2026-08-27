import os

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_DEFAULT_PASSWORD", "test-password")

import pytest

from app.models.creative_memory import CreativeMemoryItem
from app.models.novel import NovelProject, Volume
from app.models.user import User
from app.schemas.creative_memory import CreativeMemoryUpdate
from app.services.creative_memory_service import CreativeMemoryService


@pytest.mark.asyncio
async def test_generation_only_includes_confirmed_relevant_scopes(db_session):
    user = User(id=101, username="memory-owner", hashed_password="x")
    project = NovelProject(id="memory-project", user_id=user.id, title="记忆测试", initial_prompt="")
    volume = Volume(
        project_id=project.id,
        position=1,
        name="第一卷",
        start_chapter=1,
        end_chapter=5,
    )
    db_session.add_all([user, project, volume])
    await db_session.commit()

    def item(**kwargs):
        item_status = kwargs.pop("status", "active")
        item_scope = kwargs.pop("scope", "novel")
        item_title = kwargs.pop("title", "规则")
        item_content = kwargs.pop("content", "使用克制的动作描写")
        return CreativeMemoryItem(
            user_id=user.id,
            source_project_id=project.id,
            status=item_status,
            confidence=0.9,
            category="style",
            scope=item_scope,
            title=item_title,
            content=item_content,
            dedupe_key=kwargs.pop("dedupe_key"),
            **kwargs,
        )

    author = item(
        project_id=None,
        scope="author",
        title="作者习惯",
        content="避免上帝视角",
        dedupe_key="author-key",
    )
    novel = item(project_id=project.id, dedupe_key="novel-key")
    volume_item = item(
        project_id=project.id,
        scope="volume",
        volume_number=1,
        title="本卷规则",
        content="每章只推进一个主要冲突",
        dedupe_key="volume-key",
    )
    other_volume = item(
        project_id=project.id,
        scope="volume",
        volume_number=2,
        title="其他卷",
        content="不应命中",
        dedupe_key="other-volume-key",
    )
    candidate = item(
        project_id=project.id,
        scope="novel",
        status="candidate",
        title="待确认",
        content="候选规则不应注入",
        dedupe_key="candidate-key",
    )
    db_session.add_all([author, novel, volume_item, other_volume, candidate])
    await db_session.commit()

    service = CreativeMemoryService(db_session)
    selected = await service.active_for_generation(
        user_id=user.id, project_id=project.id, chapter_number=3
    )
    selected_ids = {item.id for item in selected}
    assert author.id in selected_ids
    assert novel.id in selected_ids
    assert volume_item.id in selected_ids
    assert other_volume.id not in selected_ids
    assert candidate.id not in selected_ids

    receipt = await service.build_generation_context(
        user_id=user.id, project_id=project.id, chapter_number=3
    )
    assert set(receipt["memory_ids"]) == selected_ids
    assert "候选规则不应注入" not in receipt["prompt"]
    assert receipt["receipt_id"]


@pytest.mark.asyncio
async def test_candidate_requires_explicit_activation_and_scope_target(db_session):
    user = User(id=102, username="memory-editor", hashed_password="x")
    project = NovelProject(id="memory-editor-project", user_id=user.id, title="编辑测试", initial_prompt="")
    db_session.add_all([user, project])
    await db_session.commit()
    candidate = CreativeMemoryItem(
        user_id=user.id,
        project_id=project.id,
        source_project_id=project.id,
        scope="novel",
        category="style",
        title="候选",
        content="少用形容词堆叠",
        status="candidate",
        confidence=0.8,
        dedupe_key="editor-candidate",
    )
    db_session.add(candidate)
    await db_session.commit()

    updated = await CreativeMemoryService(db_session).update_item(
        item=candidate,
        project_id=project.id,
        payload=CreativeMemoryUpdate(status="active", scope="chapter", chapter_number=4),
    )
    assert updated.status == "active"
    assert updated.scope == "chapter"
    assert updated.chapter_number == 4
    assert updated.project_id == project.id

    selected = await CreativeMemoryService(db_session).active_for_generation(
        user_id=user.id, project_id=project.id, chapter_number=3
    )
    assert updated.id not in {item.id for item in selected}
    selected = await CreativeMemoryService(db_session).active_for_generation(
        user_id=user.id, project_id=project.id, chapter_number=4
    )
    assert updated.id in {item.id for item in selected}


@pytest.mark.asyncio
async def test_author_memory_can_be_managed_from_another_owned_project(db_session):
    user = User(id=103, username="memory-global", hashed_password="x")
    source = NovelProject(id="memory-source-project", user_id=user.id, title="来源书", initial_prompt="")
    target = NovelProject(id="memory-target-project", user_id=user.id, title="目标书", initial_prompt="")
    db_session.add_all([user, source, target])
    await db_session.commit()

    author_item = CreativeMemoryItem(
        user_id=user.id,
        project_id=None,
        source_project_id=source.id,
        scope="author",
        category="style",
        title="全局写法",
        content="保持第三人称限知视角",
        status="active",
        confidence=1.0,
        dedupe_key="global-author-memory",
    )
    db_session.add(author_item)
    await db_session.commit()

    service = CreativeMemoryService(db_session)
    managed = await service.get_owned_item(
        memory_id=author_item.id,
        user_id=user.id,
        project_id=target.id,
    )
    assert managed is not None
    updated = await service.update_item(
        item=managed,
        project_id=target.id,
        payload=CreativeMemoryUpdate(pinned=True),
    )
    assert updated.project_id is None
    assert updated.source_project_id == source.id
    assert updated.pinned is True
