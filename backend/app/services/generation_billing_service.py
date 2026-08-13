# AIMETA P=生成计费服务_按模型+润色算积分并扣减退款|R=compute_generation_cost,charge_generation,refund_generation,refund_polish_surcharge|X=internal|A=服务函数|D=sqlalchemy|S=db
"""章节生成的积分计费：成本 = 模型积分价 +(润色? 润色单价 :0)，× 章数。

设计要点：
- **向后兼容**：未指定 model_code（前端 Phase 4 才下发）→ 成本 0 → 不扣费、不阻断，
  对现有生成请求零行为变化。
- **幂等**：扣减/退款都按 (reason, ref_key=task_id) 幂等（复用 QuotaService + CreditLog 唯一约束）。
- **付费必交付**：润色是勾选即计费的附加项。若实际没润色成功（通道故障/空响应/
  产出非正文/合并进 optimizer 而 optimizer 失败），由 refund_polish_surcharge 退回
  这笔附加费——章节照常交付，只退没兑现的那部分。整单退款与按项退款互斥，
  且累计退款额永不超过原扣费。
- 已知边界：生成失败已退款后，网关用同 task_id 重试若成功则不再重扣（偏向用户，可后续收紧）。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.credit_log import CreditLog
from .quota_service import QuotaService

logger = logging.getLogger(__name__)

# 扣费流水备注里写入润色单价，退款时据此精确回退。
# 不依赖“退款时再查一次 credits.price.polish”：管理员改价后会退错金额。
_POLISH_UNIT_MARKER = "polish_unit="
_POLISH_UNIT_RE = re.compile(rf"{_POLISH_UNIT_MARKER}(\d+)")


def _polish_unit_from_note(note: Optional[str]) -> int:
    """从扣费备注里解析润色单价；没有标记（未买润色 / 老流水）→ 0。"""
    if not note:
        return 0
    match = _POLISH_UNIT_RE.search(note)
    return int(match.group(1)) if match else 0


async def _refunded_total(session: AsyncSession, ref_key: str) -> int:
    """该次扣费已退还的总额（含整单退款与各类按项退款）。"""
    rows = (
        await session.execute(
            select(CreditLog.delta).where(
                CreditLog.reason == "refund",
                CreditLog.ref_key.in_([ref_key, _polish_ref(ref_key)]),
            )
        )
    ).scalars().all()
    return sum(int(d) for d in rows if int(d) > 0)


def _polish_ref(ref_key: str) -> str:
    """按项退款用独立 ref_key：CreditLog 的 (reason, ref_key) 唯一约束意味着
    同一 ref_key 只能退一次，整单退款与润色退款必须各占一个键。"""
    return f"{ref_key}:polish"


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
    from ..api.routers.model_catalog import _polish_price

    cost = await compute_generation_cost(session, model_code, enable_polish, chapters)
    if cost <= 0:
        return 0
    note = f"生成 模型={model_code} ×{chapters}章"
    if enable_polish:
        # 单价写进备注：润色若未兑现要按当时的价钱退，不能用退款时刻的价钱
        note += f"+润色 {_POLISH_UNIT_MARKER}{await _polish_price(session)}"
    await QuotaService(session).consume_credits(
        user_id, cost, reason="generate", ref_key=ref_key, note=note
    )
    return cost


def polish_undelivered(result: Any) -> bool:
    """本次生成的润色是否没兑现（据此决定退不退附加费）。

    未兑现的三种真实形态都会落在 review_summaries["polish"].applied != True：
    通道故障抛异常、模型回空、产出不是正文；此外「压根没有 polish 记录」说明
    这条分支根本没跑润色步。拿不到 review_summaries 时保守判为已兑现——
    宁可漏退也不要凭一个结构异常就乱退钱。
    """
    if not isinstance(result, dict):
        return False
    summaries = result.get("review_summaries")
    if not isinstance(summaries, dict):
        return False
    report = summaries.get("polish")
    if report is None:
        return True
    if isinstance(report, dict):
        return report.get("applied") is not True
    return False


async def _charge_row(session: AsyncSession, ref_key: str) -> Optional[CreditLog]:
    """该 ref_key 对应的扣费流水；没扣过或不是扣减则 None。"""
    row = (
        await session.execute(
            select(CreditLog).where(CreditLog.reason == "generate", CreditLog.ref_key == ref_key)
        )
    ).scalar_one_or_none()
    return row if row is not None and row.delta < 0 else None


async def refund_generation(session: AsyncSession, user_id: int, *, ref_key: Optional[str]) -> int:
    """生成失败/取消退款：按 ref_key 找原扣费记录、退还其额度（幂等）。未扣过则 no-op。

    扣掉此前已按项退过的部分（如润色未交付退款），避免同一笔扣费被退超。
    """
    if not ref_key:
        return 0
    svc = QuotaService(session)
    if await svc._credit_log_exists("refund", ref_key):
        return 0  # 已退过 → 幂等 no-op
    row = await _charge_row(session, ref_key)
    if row is None:
        return 0  # 没扣过 → 不退
    amount = -int(row.delta) - await _refunded_total(session, ref_key)
    if amount <= 0:
        return 0  # 已按项退完
    await svc.refund_credits(user_id, amount, ref_key=ref_key, reason="refund", note="生成失败/取消退款")
    return amount


async def refund_polish_surcharge(
    session: AsyncSession,
    user_id: int,
    *,
    ref_key: Optional[str],
    chapters: int = 1,
) -> int:
    """润色附加费退款：章节交付了但润色没兑现（付费必交付）。

    只退润色那部分，章节内容与其余费用不动。整单退款已发生则 no-op；
    累计退款额受原扣费封顶，批量场景下按未兑现的章数计退。
    """
    if not ref_key:
        return 0
    svc = QuotaService(session)
    polish_ref = _polish_ref(ref_key)
    if await svc._credit_log_exists("refund", polish_ref):
        return 0  # 幂等：已退过润色
    if await svc._credit_log_exists("refund", ref_key):
        return 0  # 整单已退（失败/取消/残章）→ 不再叠加
    row = await _charge_row(session, ref_key)
    if row is None:
        return 0
    unit = _polish_unit_from_note(row.note)
    if unit <= 0:
        return 0  # 本次扣费不含润色附加费
    remaining = -int(row.delta) - await _refunded_total(session, ref_key)
    amount = min(unit * max(1, int(chapters or 1)), remaining)
    if amount <= 0:
        return 0
    await svc.refund_credits(
        user_id, amount, ref_key=polish_ref, reason="refund", note="润色未交付退款"
    )
    logger.info("润色未交付，已退还附加费 %d 积分: user=%s ref=%s", amount, user_id, ref_key)
    return amount
