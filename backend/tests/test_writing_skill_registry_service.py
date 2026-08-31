import pytest

from app.services.writing_skill_registry_service import WritingSkillRegistryService


@pytest.mark.asyncio
async def test_defaults_are_seeded_and_drafts_are_not_resolved(db_session):
    registry = WritingSkillRegistryService()
    await registry.ensure_defaults(db_session)
    await db_session.commit()

    catalog = await registry.catalog(db_session)
    assert {item["id"] for item in catalog} >= {"limited_pov", "restrained_prose", "natural_closing"}

    draft = await registry.create_draft(
        db_session,
        "limited_pov",
        user_id=1,
        payload={"phase": "pre_prompt", "rules": ["只写可感知事实"]},
        source="ai_suggestion",
    )
    await db_session.commit()
    assert draft["status"] == "draft"
    resolved = await registry.resolve_selection(db_session, [{"skill_id": "limited_pov"}])
    assert resolved[0]["version_id"] != draft["id"]
    assert resolved[0]["version_snapshot"]["status"] == "published"


@pytest.mark.asyncio
async def test_publish_retires_previous_and_rollback_creates_new_version(db_session):
    registry = WritingSkillRegistryService()
    await registry.ensure_defaults(db_session)
    draft = await registry.create_draft(
        db_session,
        "natural_closing",
        user_id=1,
        payload={"phase": "verify", "rules": ["以动作收尾"], "prohibitions": ["不总结"]},
    )
    published = await registry.publish(db_session, "natural_closing", draft["id"], user_id=1, is_admin=True)
    await db_session.commit()
    assert published["status"] == "published"
    versions = await registry.list_versions(db_session, "natural_closing")
    assert sum(item["status"] == "published" for item in versions) == 1
    initial = next(item for item in versions if item["version_number"] == 1)

    rollback = await registry.rollback(db_session, "natural_closing", initial["id"], user_id=1, is_admin=True)
    await db_session.commit()
    assert rollback["status"] == "published"
    assert rollback["source"] == "rollback"
    assert rollback["id"] != initial["id"]
    versions = await registry.list_versions(db_session, "natural_closing")
    assert sum(item["status"] == "published" for item in versions) == 1


@pytest.mark.asyncio
async def test_usage_metrics_capture_acceptance(db_session):
    registry = WritingSkillRegistryService()
    await registry.ensure_defaults(db_session)
    await registry.record_usage(
        db_session, skill_key="restrained_prose", version_id=1, user_id=1,
        project_id=None, chapter_number=2, source="manual_transform",
        changed=True, accepted=True, before_score=70, after_score=88,
    )
    await registry.record_usage(
        db_session, skill_key="restrained_prose", version_id=1, user_id=1,
        project_id=None, chapter_number=3, source="generation",
        changed=False, accepted=False, before_score=80, after_score=78,
    )
    await db_session.commit()
    metrics = await registry.metrics(db_session, "restrained_prose")
    assert metrics["usage_count"] == 2
    assert metrics["accepted_count"] == 1
    assert metrics["acceptance_rate"] == 0.5


@pytest.mark.asyncio
async def test_project_copy_is_scoped_and_resolves_its_published_snapshot(db_session):
    registry = WritingSkillRegistryService()
    await registry.ensure_defaults(db_session)
    copy = await registry.fork_for_project(
        db_session,
        "restrained_prose",
        project_id="project-a",
        user_id=7,
        payload={"rules": ["每段至少一个动作"]},
    )
    await db_session.commit()
    assert copy["scope"] == "project"
    assert copy["is_project_copy"] is True
    resolved = await registry.resolve_selection(
        db_session, [{"skill_id": copy["id"]}], project_id="project-a", user_id=7
    )
    assert resolved[0]["skill_id"] == copy["id"]
    denied = await registry.resolve_selection(
        db_session, [{"skill_id": copy["id"]}], project_id="project-a", user_id=8
    )
    assert denied == []
