"""实体注册表接线与别名护栏回归 (W3/2.7)。

覆盖：
- replace_blueprint 落库后蓝图角色/地点已注册进 EntityRegistry（upsert，禁止 delete-all），
  重复调用不产生重复实体，手写亦称在再次同步后仍在；
- upsert_character_lock：改名时旧正式名收成别名；
- format_name_lock / prompt [人设锁]；visibility 吃 alias_map；
- apply_alias_replacements 护栏：跳过单字别名 / 正式名子串风险别名，安全项正常替换；
- resolve_alias 短名阈值：2 字名仅精确匹配，3 字名距离<=1，长名沿用 max(2, len//3)。
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

import app.models  # noqa: F401  触发全部 mapper 注册
import app.models.user_quota  # noqa: F401  防 mapper KeyError

from app.models.entity_registry import EntityAlias, EntityRegistry
from app.schemas.novel import Blueprint
from app.services.entity_registry_service import EntityRegistryService
from app.services.prompt_assembly_service import PromptAssemblyService
from app.services.writer_context_builder import WriterContextBuilder


def _blueprint() -> Blueprint:
    return Blueprint(
        title="测试书",
        characters=[
            {"name": "顾远", "identity": "主角"},
            {"name": "沈青梧", "identity": "女主"},
        ],
        world_setting={"key_locations": [{"name": "云京城", "description": "帝都"}]},
    )


class _DummyCache:
    async def invalidate_project_schema(self, project_id):
        return True


# ----------------------------------------------------------------- 蓝图接线
@pytest.mark.asyncio
async def test_replace_blueprint_registers_entities_idempotent(db_session, monkeypatch):
    """蓝图落库即注册实体，且重复落库不翻倍（upsert 幂等）。"""
    from app.services import novel_service as novel_service_module

    monkeypatch.setattr(novel_service_module, "CacheService", _DummyCache)
    service = novel_service_module.NovelService(db_session)

    await service.replace_blueprint("proj-w3", _blueprint())

    count_stmt = (
        select(func.count())
        .select_from(EntityRegistry)
        .where(EntityRegistry.project_id == "proj-w3")
    )
    assert (await db_session.execute(count_stmt)).scalar_one() == 3  # 2 角色 + 1 地点

    rows = (
        await db_session.execute(
            select(EntityRegistry).where(EntityRegistry.project_id == "proj-w3")
        )
    ).scalars().all()
    assert {r.canonical_name for r in rows} == {"顾远", "沈青梧", "云京城"}
    assert all(r.source == "blueprint" for r in rows)

    # 幂等：重复落库不产生重复实体
    await service.replace_blueprint("proj-w3", _blueprint())
    assert (await db_session.execute(count_stmt)).scalar_one() == 3


async def _alias_names(session, project_id: str, canonical_name: str) -> set[str]:
    result = await session.execute(
        select(EntityAlias.alias)
        .join(EntityRegistry)
        .where(
            EntityRegistry.project_id == project_id,
            EntityRegistry.canonical_name == canonical_name,
        )
    )
    return set(result.scalars().all())


@pytest.mark.asyncio
async def test_replace_blueprint_keeps_handwritten_aliases(db_session, monkeypatch):
    """再次同步蓝图不得 delete-all，手写亦称必须还在。"""
    from app.services import novel_service as novel_service_module

    monkeypatch.setattr(novel_service_module, "CacheService", _DummyCache)
    service = novel_service_module.NovelService(db_session)
    registry = EntityRegistryService(db_session)

    await service.replace_blueprint("proj-alias", _blueprint())
    entity = await registry._find_by_name("proj-alias", "顾远", entity_type="character")
    assert entity is not None
    await registry._add_aliases(entity.id, ["顾公子", "远哥"])
    await db_session.commit()

    await service.replace_blueprint("proj-alias", _blueprint())
    assert await _alias_names(db_session, "proj-alias", "顾远") == {"顾公子", "远哥"}


@pytest.mark.asyncio
async def test_upsert_character_lock_rename_old_name_becomes_alias(db_session):
    """Codex 改正式名：旧名收成别名，新名成为 canonical。"""
    registry = EntityRegistryService(db_session)
    await registry.register_entity(
        project_id="proj-lock",
        entity_type="character",
        canonical_name="顾远",
        aliases=["顾公子"],
        source="blueprint",
    )
    await db_session.commit()

    await registry.upsert_character_lock(
        project_id="proj-lock",
        canonical_name="顾远舟",
        previous_name="顾远",
        aliases=["远哥"],
        replace_aliases=True,
        source="manual",
    )
    await db_session.commit()

    renamed = await registry._find_by_name("proj-lock", "顾远舟", entity_type="character")
    assert renamed is not None
    aliases = await _alias_names(db_session, "proj-lock", "顾远舟")
    assert "顾远" in aliases
    assert "远哥" in aliases
    assert await registry.resolve_alias("proj-lock", "顾远") == "顾远舟"
    assert await registry._find_by_name("proj-lock", "顾远", entity_type="character") is None


def test_format_name_lock_only_lists_aliased_characters():
    with_alias = SimpleNamespace(
        entity_type="character",
        is_active=True,
        canonical_name="顾远",
        aliases=[SimpleNamespace(alias="顾公子"), SimpleNamespace(alias="远哥")],
    )
    no_alias = SimpleNamespace(
        entity_type="character",
        is_active=True,
        canonical_name="沈青梧",
        aliases=[],
    )
    location = SimpleNamespace(
        entity_type="location",
        is_active=True,
        canonical_name="云京城",
        aliases=[SimpleNamespace(alias="帝都")],
    )
    text = EntityRegistryService.format_name_lock([with_alias, no_alias, location])
    assert "顾远（亦称：顾公子、远哥）" in text
    assert "沈青梧" not in text
    assert "云京城" not in text
    assert EntityRegistryService.format_name_lock([no_alias]) == ""


def test_prompt_assembly_includes_name_lock_section():
    service = PromptAssemblyService(prompt_service=None, llm_service=None)
    sections = service.build_prompt_sections(
        writer_blueprint={"title": "书名"},
        previous_summary="上一章",
        previous_tail="上一章结尾",
        chapter_mission=None,
        mission_brief_text="任务书",
        rag_context=None,
        outline_title="第三十一章",
        outline_summary="顾公子在茶楼",
        writing_notes="",
        forbidden_characters=[],
        project_memory_text=None,
        memory_context=None,
        platinum_writing_brief=None,
        platinum_rhythm_brief=None,
        foreshadowing_urgency_brief=None,
        hook_continuity_brief=None,
        emotion_expression_brief=None,
        name_lock_text="顾远（亦称：顾公子、远哥）",
    )
    titled = {title: body for title, body in sections}
    lock_title = next(title for title in titled if "人设锁" in title)
    assert "顾远（亦称：顾公子、远哥）" in titled[lock_title]


def test_visibility_consumes_alias_map():
    """大纲只写昵称时，有 alias_map 才能把正式名角色卡留在可见蓝图里。"""
    builder = WriterContextBuilder()
    blueprint = {"characters": [{"name": "顾远", "identity": "主角"}]}
    without_map = builder.build_visibility_context(
        blueprint=blueprint,
        completed_summaries=[],
        previous_tail="",
        outline_title="第三十一章",
        outline_summary="顾公子在茶楼遇见故人",
        writing_notes="",
        allowed_new_characters=[],
    )
    assert without_map["writer_blueprint"]["characters"] == []
    assert "顾远" not in without_map["planned_characters"]

    with_map = builder.build_visibility_context(
        blueprint=blueprint,
        completed_summaries=[],
        previous_tail="",
        outline_title="第三十一章",
        outline_summary="顾公子在茶楼遇见故人",
        writing_notes="",
        allowed_new_characters=[],
        alias_map={"顾公子": "顾远", "顾远": "顾远"},
    )
    assert [c["name"] for c in with_map["writer_blueprint"]["characters"]] == ["顾远"]
    assert "顾远" in with_map["planned_characters"]


# ----------------------------------------------------------------- 替换护栏
def test_apply_alias_replacements_guardrails():
    """子串风险别名与单字别名被跳过，安全别名正常替换。"""
    alias_map = {
        "王小明": "王小明",   # 恒等映射：跳过
        "小明": "王小明",     # 正式名「王小明」的子串：跳过（否则「王小明」→「王王小明」）
        "明": "王小明",       # 单字：跳过
        "阿远": "顾远",       # 安全项：替换
        "顾远": "顾远",       # 恒等映射：跳过
    }
    content = "王小明和阿远同行，小明在前。"
    result = EntityRegistryService.apply_alias_replacements(content, alias_map)
    assert result == "王小明和顾远同行，小明在前。"


def test_apply_alias_replacements_degrades_on_empty():
    """空正文/空映射原样返回，不抛错。"""
    assert EntityRegistryService.apply_alias_replacements("", {"a": "b"}) == ""
    assert EntityRegistryService.apply_alias_replacements("正文", {}) == "正文"


# ----------------------------------------------------------------- 短名消歧阈值
@pytest.mark.asyncio
async def test_resolve_alias_short_name_thresholds(db_session):
    """2 字名不再任意换字误匹配；3 字名距离<=1 才匹配。"""
    registry = EntityRegistryService(db_session)
    await registry.register_entity(
        project_id="proj-w3b", entity_type="character", canonical_name="李四",
    )
    await registry.register_entity(
        project_id="proj-w3b", entity_type="character", canonical_name="沈青梧",
    )

    # 2 字名：旧阈值 max(2, 0)=2 会把「李五」误配到「李四」，现要求精确匹配
    assert await registry.resolve_alias("proj-w3b", "李五") is None
    assert await registry.resolve_alias("proj-w3b", "李四") == "李四"

    # 3 字名：距离 1 匹配，距离 2 拒绝
    assert await registry.resolve_alias("proj-w3b", "沈青雾") == "沈青梧"
    assert await registry.resolve_alias("proj-w3b", "陈清梧") is None
