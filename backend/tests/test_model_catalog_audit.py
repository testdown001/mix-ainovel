"""模型目录配置体检。

2026-08-13 线上真实事故：目录三档（章鱼1.0/2.0/3.0）的 real_model 是 gpt-5.4/5.5/5.6，
base_url 全留空 → 继承默认通道 api.deepseek.com → 上游以「不支持该模型名」拒绝 →
兜底通道 grok-4.5 悄悄代写。结果是用户按 6/10/18 三种价位买到的是同一个兜底模型，
而「通道实时健康」全绿，实调用测不出来。这里锁住能从配置本身看出这件事。
"""
import pytest
from sqlalchemy import select

from app.models.model_catalog import ModelCatalog
from app.models.system_config import SystemConfig
from app.services.llm_channel_audit import _model_family, audit_llm_config


class TestModelFamily:
    @pytest.mark.parametrize("model,family", [
        ("gpt-5.4", "gpt"),
        ("deepseek-v4-flash", "deepseek"),
        ("claude-opus-4-20250514", "claude"),
        ("grok-4.5", "grok"),
        ("gemini-2.5-pro", "gemini"),
        ("glm-4.6", "glm"),
        ("qwen-max", "qwen"),
        ("o3-mini", "o"),
        ("", ""),
        (None, ""),
        ("4o", ""),  # 数字开头无族名，粗判放过而不是乱猜
    ])
    def test_prefix(self, model, family):
        assert _model_family(model) == family


async def _seed_channel(session, base_url="https://api.deepseek.com", model="deepseek-v4-flash"):
    session.add(SystemConfig(key="llm.api_key", value="sk-test"))
    session.add(SystemConfig(key="llm.base_url", value=base_url))
    session.add(SystemConfig(key="llm.model", value=model))
    # 兜底配成另一家，避免假冗余告警混进断言
    session.add(SystemConfig(key="llm_fallback.api_key", value="sk-fb"))
    session.add(SystemConfig(key="llm_fallback.base_url", value="https://pavv.me/v1"))
    session.add(SystemConfig(key="llm_fallback.model", value="grok-4.5"))
    session.add(SystemConfig(key="embedding.api_key", value="sk-emb"))
    await session.commit()


def _catalog(code, real_model, *, base_url=None, price=6, tier="free", active=True, name=None):
    return ModelCatalog(
        code=code,
        display_name=name or code,
        real_model=real_model,
        base_url=base_url,
        credit_price=price,
        min_tier=tier,
        is_active=active,
    )


def _codes(findings):
    return {f["code"] for f in findings}


@pytest.mark.asyncio
class TestCatalogAudit:
    async def test_flags_the_real_incident(self, db_session):
        """gpt-* 目录条目 + deepseek 默认通道 + 空 base_url = 必然被上游拒绝。"""
        await _seed_channel(db_session)
        db_session.add_all([
            _catalog("octopus_v1", "gpt-5.4", price=6, name="章鱼1.0"),
            _catalog("octopus_v2", "gpt-5.5", price=10, tier="creator", name="章鱼2.0"),
            _catalog("octopus_v3", "gpt-5.6", price=18, tier="flagship", name="章鱼3.0"),
        ])
        await db_session.commit()

        findings = await audit_llm_config(db_session)
        assert "catalog_model_endpoint_mismatch" in _codes(findings)
        finding = next(f for f in findings if f["code"] == "catalog_model_endpoint_mismatch")
        assert finding["level"] == "error"
        # 三条都要点名，管理员才知道要改哪几行
        for name in ("章鱼1.0", "章鱼2.0", "章鱼3.0"):
            assert name in finding["detail"]

    async def test_same_family_is_clean(self, db_session):
        await _seed_channel(db_session)
        db_session.add_all([
            _catalog("v1", "deepseek-v4-flash", price=6),
            _catalog("v2", "deepseek-v4-pro", price=10),
        ])
        await db_session.commit()
        assert "catalog_model_endpoint_mismatch" not in _codes(await audit_llm_config(db_session))

    async def test_own_base_url_is_admins_business(self, db_session):
        """条目自带 base_url 时不继承默认通道，跨族是完全合法的配置。"""
        await _seed_channel(db_session)
        db_session.add(_catalog("v1", "gpt-5.4", base_url="https://api.openai.com/v1"))
        await db_session.commit()
        assert "catalog_model_endpoint_mismatch" not in _codes(await audit_llm_config(db_session))

    async def test_inactive_rows_ignored(self, db_session):
        await _seed_channel(db_session)
        db_session.add(_catalog("v1", "gpt-5.4", active=False))
        await db_session.commit()
        assert "catalog_model_endpoint_mismatch" not in _codes(await audit_llm_config(db_session))

    async def test_blank_real_model_inherits_channel_model(self, db_session):
        """real_model 留空 = 用通道自己的模型，不可能错配。"""
        await _seed_channel(db_session)
        db_session.add(_catalog("v1", None))
        await db_session.commit()
        assert "catalog_model_endpoint_mismatch" not in _codes(await audit_llm_config(db_session))

    async def test_duplicate_target_flagged(self, db_session):
        """不同价位解析到同一 (地址, 模型)：用户付不同积分买到同一个模型。"""
        await _seed_channel(db_session)
        db_session.add_all([
            _catalog("v1", "deepseek-v4-flash", price=6, name="章鱼1.0"),
            _catalog("v2", "deepseek-v4-flash", price=18, tier="flagship", name="章鱼3.0"),
        ])
        await db_session.commit()

        findings = await audit_llm_config(db_session)
        assert "catalog_duplicate_target" in _codes(findings)
        detail = next(f for f in findings if f["code"] == "catalog_duplicate_target")["detail"]
        assert "6分" in detail and "18分" in detail

    async def test_distinct_targets_clean(self, db_session):
        await _seed_channel(db_session)
        db_session.add_all([
            _catalog("v1", "deepseek-v4-flash", price=6),
            _catalog("v2", "deepseek-v4-pro", price=18),
        ])
        await db_session.commit()
        assert "catalog_duplicate_target" not in _codes(await audit_llm_config(db_session))

    async def test_blank_real_model_pair_is_duplicate(self, db_session):
        """两条都留空 real_model → 都落到通道模型上，同样是假阶梯。"""
        await _seed_channel(db_session)
        db_session.add_all([_catalog("v1", None, price=6), _catalog("v2", None, price=18)])
        await db_session.commit()
        assert "catalog_duplicate_target" in _codes(await audit_llm_config(db_session))

    async def test_empty_catalog_clean(self, db_session):
        await _seed_channel(db_session)
        findings = await audit_llm_config(db_session)
        assert "catalog_model_endpoint_mismatch" not in _codes(findings)
        assert "catalog_duplicate_target" not in _codes(findings)

    async def test_errors_sort_before_warnings(self, db_session):
        await _seed_channel(db_session)
        db_session.add_all([
            _catalog("v1", "gpt-5.4", price=6, name="章鱼1.0"),
            _catalog("v2", "gpt-5.4", price=18, name="章鱼3.0"),
        ])
        await db_session.commit()
        findings = await audit_llm_config(db_session)
        levels = [f["level"] for f in findings]
        assert levels == sorted(levels, key=lambda l: {"error": 0, "warn": 1, "info": 2}[l])

    async def test_catalog_table_missing_does_not_break_audit(self, db_session, monkeypatch):
        """体检本身不能因为目录查询失败而整体失败——它还要报别的问题。"""
        await _seed_channel(db_session)
        original = db_session.execute

        async def _boom(stmt, *a, **kw):
            if getattr(getattr(stmt, "column_descriptions", [{}])[0].get("entity", None), "__name__", "") == "ModelCatalog":
                raise RuntimeError("no such table")
            return await original(stmt, *a, **kw)

        monkeypatch.setattr(db_session, "execute", _boom)
        findings = await audit_llm_config(db_session)
        assert isinstance(findings, list)  # 未抛异常
        assert "catalog_model_endpoint_mismatch" not in _codes(findings)


@pytest.mark.asyncio
async def test_seeded_rows_are_visible(db_session):
    """夹具自检：确认 catalog 行确实落库（否则上面的"未告警"断言会变成假通过）。"""
    await _seed_channel(db_session)
    db_session.add(_catalog("v1", "gpt-5.4"))
    await db_session.commit()
    rows = (await db_session.execute(select(ModelCatalog))).scalars().all()
    assert len(rows) == 1
