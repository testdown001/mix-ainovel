"""M0/M1 路线图基础设施回归测试。"""
from __future__ import annotations

import pytest

from app.core.error_codes import DomainErrorCode, api_error
from app.models.novel import Chapter, ChapterOutline, ChapterVersion, NovelBlueprint, NovelProject
from app.models.user import User
from app.schemas.world_state import WorldStateSnapshotCreateRequest
from app.services.volume_service import VolumeService
from app.services.world_state_service import WorldStateService


async def _seed_project(db_session, *, suffix: str = "m1") -> NovelProject:
    user = User(
        id=7101 if suffix == "m1" else 7102,
        username=f"roadmap-{suffix}",
        email=f"roadmap-{suffix}@example.com",
        hashed_password="test-hash",
    )
    project = NovelProject(
        id=f"roadmap-{suffix}-project",
        user_id=user.id,
        title="路线图测试作品",
        initial_prompt="测试 M0/M1",
    )
    db_session.add_all([user, project])
    await db_session.flush()
    return project


@pytest.mark.asyncio
async def test_volume_entity_backfills_json_and_assigns_chapters(db_session):
    project = await _seed_project(db_session)
    blueprint = NovelBlueprint(
        project_id=project.id,
        volumes=[
            {"name": "开局卷", "start_chapter": 1, "end_chapter": 2, "arc_goal": "立住冲突"},
            {"name": "反击卷", "start_chapter": 3, "end_chapter": 5, "climax_hint": "夺回主场"},
        ],
    )
    outlines = [
        ChapterOutline(project_id=project.id, chapter_number=1, title="一", summary="开场"),
        ChapterOutline(project_id=project.id, chapter_number=3, title="三", summary="反击"),
    ]
    chapters = [
        Chapter(project_id=project.id, chapter_number=1),
        Chapter(project_id=project.id, chapter_number=3),
    ]
    db_session.add_all([blueprint, *outlines, *chapters])
    await db_session.flush()

    service = VolumeService(db_session)
    volumes = await service.sync_from_blueprint(blueprint)
    await db_session.flush()

    assert [(item.position, item.name) for item in volumes] == [(1, "开局卷"), (2, "反击卷")]
    assert outlines[0].volume_id == volumes[0].id
    assert outlines[1].volume_id == volumes[1].id
    assert chapters[0].volume_id == volumes[0].id
    assert chapters[1].volume_id == volumes[1].id
    assert [item.sort_key for item in [*outlines, *chapters]] == [1000, 3000, 1000, 3000]
    assert blueprint.volumes[0]["id"] == volumes[0].id
    assert blueprint.volumes[1]["volume_number"] == 2

    # 编辑器只回传基础规划时，已产生的重规划必须保留。
    volumes[1].replan = {"focus": "先处理内鬼", "status": "pending"}
    blueprint.volumes = [
        {"name": "开局卷（修订）", "start_chapter": 1, "end_chapter": 2},
        {"name": "反击卷", "start_chapter": 3, "end_chapter": 5},
    ]
    refreshed = await service.sync_from_blueprint(blueprint)
    assert refreshed[1].replan == {"focus": "先处理内鬼", "status": "pending"}
    assert blueprint.volumes[1]["replan"]["focus"] == "先处理内鬼"


@pytest.mark.asyncio
async def test_world_state_is_immutable_and_next_chapter_reads_previous_seed(db_session):
    project = await _seed_project(db_session, suffix="state")
    first = Chapter(project_id=project.id, chapter_number=1)
    second = Chapter(project_id=project.id, chapter_number=2)
    db_session.add_all([first, second])
    await db_session.flush()
    version = ChapterVersion(chapter_id=first.id, content="陆沉在城门外拔剑。")
    db_session.add(version)
    await db_session.flush()

    service = WorldStateService(db_session)
    first_snapshot = await service.create_snapshot(
        project.id,
        1,
        WorldStateSnapshotCreateRequest.model_validate(
            {
                "source_version_id": version.id,
                "origin": "manual",
                "state": {
                    "characters": [
                        {
                            "name": "陆沉",
                            "location": "城门外",
                            "evidence": [{"label": "拔剑", "range": {"char_start": 0, "char_end": 8}}],
                        }
                    ],
                    "facts": {"城门": "封锁"},
                },
            }
        ),
    )
    second_snapshot = await service.create_snapshot(
        project.id,
        2,
        WorldStateSnapshotCreateRequest.model_validate(
            {"state": {"facts": {"城门": "开启"}}},
        ),
    )
    await db_session.commit()

    assert first_snapshot.parent_snapshot_id is None
    assert second_snapshot.parent_snapshot_id == first_snapshot.id
    seed = await service.seed_for_chapter(project.id, 3)
    assert seed.source_snapshot_id == second_snapshot.id
    assert seed.state and seed.state.facts["城门"] == "开启"

    with pytest.raises(Exception) as exc_info:
        await service.create_snapshot(
            project.id,
            2,
            WorldStateSnapshotCreateRequest.model_validate(
                {"source_version_id": version.id, "state": {"facts": {}}}
            ),
        )
    assert getattr(exc_info.value, "status_code", None) == 409
    assert exc_info.value.detail["code"] == DomainErrorCode.WORLD_STATE_SOURCE_MISMATCH


def test_structured_error_code_contract_uses_enum_value():
    error = api_error(404, DomainErrorCode.VOLUME_NOT_FOUND, "未找到指定分卷。", meta={"position": 3})
    assert error.status_code == 404
    assert error.detail == {
        "code": "VOLUME_NOT_FOUND",
        "message": "未找到指定分卷。",
        "meta": {"position": 3},
    }
