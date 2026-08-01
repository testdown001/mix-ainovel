"""revision_hint 生命周期 (W3/2.5)：大纲重写后过时修订提示被清除。

覆盖：
- update_or_create_outline 重写既有大纲(title/summary) → 该章 metadata.revision_hint 被清除，
  其余键（如导演脚本）保留；
- 清除后读侧 build_revision_brief 不再注入（清除前能注入，证明路径真实触发）；
- 显式传 metadata 仍是整体替换语义（原行为不变）；
- 无 hint 的大纲重写 → metadata 原样保留，不误动。
"""
import pytest

import app.models  # noqa: F401  触发全部 mapper 注册
import app.models.user_quota  # noqa: F401  防 mapper KeyError

from app.models.novel import ChapterOutline
from app.services.novel_service import NovelService
from app.services.outline_revision_service import OutlineRevisionService

_PENDING_HINT = {
    "source_chapter": 4,
    "severity": "high",
    "reason": "主角已在第4章和解",
    "suggestion": "本章冲突改为暗流",
    "status": "pending",
}


async def _seed_outline(session, project_id, ch, metadata=None):
    outline = ChapterOutline(
        project_id=project_id,
        chapter_number=ch,
        title="旧标题",
        summary="旧摘要",
        metadata=metadata,
    )
    session.add(outline)
    await session.flush()
    return outline


@pytest.mark.asyncio
async def test_outline_rewrite_clears_stale_revision_hint(db_session):
    """大纲重写 = hint 依据失效：revision_hint 被清除且 metadata 其他键保留。"""
    await _seed_outline(
        db_session, "proj-hint", 5,
        metadata={"revision_hint": dict(_PENDING_HINT), "director_script": {"beats": [1, 2]}},
    )
    revision = OutlineRevisionService()

    # 清除前：读侧能注入 → 证明测试真正触发被修路径
    brief_before = await revision.build_revision_brief(
        project_id="proj-hint", chapter_number=5, session=db_session,
    )
    assert brief_before and "大纲修订提示" in brief_before

    outline = await NovelService(db_session).update_or_create_outline(
        "proj-hint", 5, "新标题", "新摘要",
    )

    assert outline.title == "新标题"
    assert outline.summary == "新摘要"
    assert "revision_hint" not in outline.metadata          # 过时 hint 已清除
    assert outline.metadata["director_script"] == {"beats": [1, 2]}  # 其他键保留

    brief_after = await revision.build_revision_brief(
        project_id="proj-hint", chapter_number=5, session=db_session,
    )
    assert brief_after is None  # 清除后读侧不再注入


@pytest.mark.asyncio
async def test_outline_rewrite_without_hint_keeps_metadata(db_session):
    """无 hint 时重写大纲不误动 metadata（传 None 保留原 metadata 语义不变）。"""
    await _seed_outline(
        db_session, "proj-hint2", 3, metadata={"director_script": {"beats": [9]}},
    )
    outline = await NovelService(db_session).update_or_create_outline(
        "proj-hint2", 3, "新标题", "新摘要",
    )
    assert outline.metadata == {"director_script": {"beats": [9]}}


@pytest.mark.asyncio
async def test_outline_update_with_explicit_metadata_merges(db_session):
    """显式传 metadata 是**合并**语义（2026-08-01 由整体替换改）。

    改动理由：outline.metadata 上还挂着别处写入的键——`prediction`（writer.py 直写）、
    导演脚本等。大纲生成开始落库 planning 字段后，若沿用整体替换，会把这些键静默抹掉。
    该形参此前在生产代码中零调用方，语义收紧不影响既有行为。
    """
    service = NovelService(db_session)
    created = await service.update_or_create_outline(
        "proj-hint3", 1, "标题", "摘要", metadata={"foo": "bar"},
    )
    assert created.metadata == {"foo": "bar"}

    updated = await service.update_or_create_outline(
        "proj-hint3", 1, "标题2", "摘要2", metadata={"baz": 1},
    )
    assert updated.metadata == {"foo": "bar", "baz": 1}  # 既有键保留

    # 同名键以新值为准
    again = await service.update_or_create_outline(
        "proj-hint3", 1, "标题3", "摘要3", metadata={"baz": 2},
    )
    assert again.metadata["baz"] == 2


@pytest.mark.asyncio
async def test_explicit_metadata_still_strips_stale_revision_hint(db_session):
    """传 metadata 的同时，过时的 revision_hint 仍须清除（两条逻辑不能互相顶掉）。"""
    await _seed_outline(
        db_session, "proj-hint4", 2,
        metadata={"revision_hint": dict(_PENDING_HINT), "prediction": {"p": 1}},
    )
    outline = await NovelService(db_session).update_or_create_outline(
        "proj-hint4", 2, "新标题", "新摘要", metadata={"planning": {"narrative_phase": "回击2"}},
    )
    assert "revision_hint" not in outline.metadata
    assert outline.metadata["prediction"] == {"p": 1}          # 别处写的键不被抹
    assert outline.metadata["planning"] == {"narrative_phase": "回击2"}


def test_strip_revision_hint_helper():
    """replace_blueprint 全量重建大纲时搬运的旧 metadata 必须剔除 stale revision_hint，保留其他键。"""
    from app.services.novel_service import NovelService

    meta = {"revision_hint": {"status": "pending", "hint": "旧建议"}, "director_script": "ds"}
    out = NovelService._strip_revision_hint(meta)
    assert "revision_hint" not in out
    assert out["director_script"] == "ds"
    assert NovelService._strip_revision_hint(None) is None
    plain = {"director_script": "ds"}
    assert NovelService._strip_revision_hint(plain) is plain
