"""实体注册表接线与别名护栏回归 (W3/2.7)。

覆盖：
- replace_blueprint 落库后蓝图角色/地点已注册进 EntityRegistry（经 _sync_blueprint_entities，
  delete source='blueprint' 再插入 = 天然幂等），重复调用不产生重复实体；
- apply_alias_replacements 护栏：跳过单字别名 / 正式名子串风险别名，安全项正常替换；
- resolve_alias 短名阈值：2 字名仅精确匹配，3 字名距离<=1，长名沿用 max(2, len//3)。
"""
import pytest
from sqlalchemy import func, select

import app.models  # noqa: F401  触发全部 mapper 注册
import app.models.user_quota  # noqa: F401  防 mapper KeyError

from app.models.entity_registry import EntityRegistry
from app.schemas.novel import Blueprint
from app.services.entity_registry_service import EntityRegistryService


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
    """蓝图落库即注册实体，且重复落库不翻倍（delete-then-insert 幂等）。"""
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
