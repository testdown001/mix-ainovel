"""默认会员套餐落库（init_db._ensure_default_plans）回归测试。

背景：DEFAULT_PLANS 之前仅作接口展示兜底（id 为字符串档位名），不是真实数据行，
导致后台「会员套餐」编辑/上下架/删除（按数字主键 PUT /api/plans/{int}）必然 422。
本测试锁定：套餐表为空时落库三档真实行（数字主键），且幂等。
"""
import json

import pytest
from sqlalchemy import select

from app.db.init_db import _ensure_default_plans
from app.models import Plan


@pytest.mark.asyncio
async def test_seed_default_plans_when_empty(db_session):
    await _ensure_default_plans(db_session)
    await db_session.commit()

    rows = (await db_session.execute(select(Plan).order_by(Plan.sort_order))).scalars().all()
    assert len(rows) == 3
    assert [r.tier for r in rows] == ["free", "creator", "flagship"]
    # 主键必须是数字（修复点：字符串 id 会让后台编辑接口 422）
    assert all(isinstance(r.id, int) for r in rows)
    # features 落库为可解析的 JSON 数组
    assert all(isinstance(json.loads(r.features), list) for r in rows)


@pytest.mark.asyncio
async def test_seed_default_plans_idempotent(db_session):
    await _ensure_default_plans(db_session)
    await db_session.commit()
    # 已存在任意套餐则不再重复落库
    await _ensure_default_plans(db_session)
    await db_session.commit()

    rows = (await db_session.execute(select(Plan))).scalars().all()
    assert len(rows) == 3
