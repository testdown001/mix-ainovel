# AIMETA P=生成计费服务_按模型+润色算积分并扣减退款|R=compute_generation_cost,charge_generation,refund_generation|X=internal|A=服务函数|D=sqlalchemy|S=db
"""章节生成的积分计费：成本 = 模型积分价 +(润色? 润色单价 :0)，× 章数。

设计要点：
- **向后兼容**：未指定 model_code（前端 Phase 4 才下发）→ 成本 0 → 不扣费、不阻断，
  对现有生成请求零行为变化。
- **幂等**：扣减/退款都按 (reason, ref_key=task_id) 幂等（复用 QuotaService + CreditLog 唯一约束）。
- 已知边界：生成失败已退款后，网关用同 task_id 重试若成功则不再重扣（偏向用户，可后续收紧）。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.credit_log import CreditLog
from .quota_service import QuotaService

logger = logging.getLogger(__name__)


async def compute_generation_cost(
    session: AsyncSession,
    model_code: Optional[str],
    enable_polish: bool,
    chapters: int = 1,
) -> int:
    """算本次生成应扣积分。未指定/未入库/下架模型 → 模型费为 0（用默认通道、不计费）；
    但勾选润色时附加费照收——否则直连 API 不带 model_code 即可免费跑润色。"""
    from ..api.routers.model_catalog import get_model_by_code, _polish_price

    per = 0
    if model_code:
        model = await get_model_by_code(session, model_code)
        if model is not None and model.is_active:
            per = int(model.credit_price or 0)
    if enable_polish:
        per += await _polish_price(session)
    return per * max(1, int(chapters or 1))


async def charge_generation(
    session: AsyncSession,
    user_id: int,
    model_code: Optional[str],
    enable_polish: bool,
    *,
    ref_key: Optional[str] = None,
    chapters: int = 1,
) -> int:
    """先扣后跑：扣减本次生成积分，返回实扣额。余额不足由 consume_credits 抛 402。
    成本为 0（未指定模型）则直接返回 0、不动账户。"""
    cost = await compute_generation_cost(session, model_code, enable_polish, chapters)
    if cost <= 0:
        return 0
    note = f"生成 模型={model_code} ×{chapters}章" + ("+润色" if enable_polish else "")
    await QuotaService(session).consume_credits(
        user_id, cost, reason="generate", ref_key=ref_key, note=note
    )
    return cost


async def refund_generation(session: AsyncSession, user_id: int, *, ref_key: Optional[str]) -> int:
    """生成失败/取消退款：按 ref_key 找原扣费记录、退还其额度（幂等）。未扣过则 no-op。"""
    if not ref_key:
        return 0
    svc = QuotaService(session)
    if await svc._credit_log_exists("refund", ref_key):
        return 0  # 已退过 → 幂等 no-op
    row = (
        await session.execute(
            select(CreditLog).where(CreditLog.reason == "generate", CreditLog.ref_key == ref_key)
        )
    ).scalar_one_or_none()
    if row is None or row.delta >= 0:
        return 0  # 没扣过 → 不退
    amount = -int(row.delta)
    await svc.refund_credits(user_id, amount, ref_key=ref_key, reason="refund", note="生成失败/取消退款")
    return amount
