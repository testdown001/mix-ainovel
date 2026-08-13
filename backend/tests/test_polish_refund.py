"""润色附加费「付费必交付」回归。

润色是勾选即计费的附加项（credits.price.polish，先扣后跑）。上游通道故障时
_run_polish 会吞掉异常、原样返回未润色的正文——章节照常交付，用户却付了润色的钱。
这组用例锁死：润色没兑现就必须把这笔附加费退回去，且不能与整单退款重复退。
"""
import pytest

import app.models  # noqa: F401  触发全部 mapper 注册
from app.services.generation_billing_service import (
    charge_generation,
    polish_undelivered,
    refund_generation,
    refund_polish_surcharge,
)
from app.services.quota_service import QuotaService

POLISH_PRICE = 5  # credits.price.polish 默认值（SystemConfig 未配置时）


# ---------------- 未兑现判定 ----------------

def test_polish_undelivered_detects_each_failure_shape():
    # 通道抛异常 / 空响应 / 产出不是正文：_run_polish 都返回 applied=False
    for reason in ("Error code: 401", "empty_response", "invalid_chapter_response"):
        result = {"review_summaries": {"polish": {"applied": False, "reason": reason}}}
        assert polish_undelivered(result) is True


def test_polish_undelivered_false_when_applied():
    assert polish_undelivered({"review_summaries": {"polish": {"applied": True}}}) is False


def test_polish_undelivered_true_when_step_never_ran():
    """收了润色的钱，评审摘要里却没有 polish 记录 → 这条分支压根没跑润色。"""
    assert polish_undelivered({"review_summaries": {"optimizer": {}}}) is True


def test_polish_undelivered_conservative_on_unknown_shape():
    """拿不到 review_summaries 时不做判断——宁可漏退，也不凭结构异常乱退钱。"""
    assert polish_undelivered({}) is False
    assert polish_undelivered({"review_summaries": None}) is False
    assert polish_undelivered(None) is False


def test_polish_undelivered_merged_into_failed_optimizer():
    """润色被合并进 optimizer 且 optimizer 失败 → 一个字都没改，必须判为未兑现。"""
    merged_fail = {
        "review_summaries": {
            "polish": {"applied": False, "merged_into_optimizer": True, "reason": "optimizer_failed"}
        }
    }
    assert polish_undelivered(merged_fail) is True


# ---------------- 退款账务 ----------------

@pytest.mark.asyncio
async def test_refunds_polish_surcharge_only(db_session):
    """章节交付、润色没兑现：只退润色那份，模型费不退。"""
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(101)
    before = (await svc.get_or_create_quota(101)).credit_total

    charged = await charge_generation(
        db_session, 101, model_code=None, enable_polish=True, ref_key="task-101"
    )
    assert charged == POLISH_PRICE  # 无 model_code → 只有润色附加费

    refunded = await refund_polish_surcharge(db_session, 101, ref_key="task-101")
    assert refunded == POLISH_PRICE
    assert (await svc.get_or_create_quota(101)).credit_total == before


@pytest.mark.asyncio
async def test_polish_refund_is_idempotent(db_session):
    """任务重投/重复判定不能退第二次。"""
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(102)
    await charge_generation(
        db_session, 102, model_code=None, enable_polish=True, ref_key="task-102"
    )

    assert await refund_polish_surcharge(db_session, 102, ref_key="task-102") == POLISH_PRICE
    assert await refund_polish_surcharge(db_session, 102, ref_key="task-102") == 0


@pytest.mark.asyncio
async def test_no_polish_refund_when_polish_not_charged(db_session):
    """没买润色 → 没有可退的附加费（哪怕结果里判定为未兑现）。"""
    await QuotaService(db_session).get_or_create_quota(103)
    await charge_generation(
        db_session, 103, model_code=None, enable_polish=False, ref_key="task-103"
    )
    assert await refund_polish_surcharge(db_session, 103, ref_key="task-103") == 0


@pytest.mark.asyncio
async def test_polish_refund_skipped_after_full_refund(db_session):
    """整单已退（生成失败/取消/残章）→ 不再叠加退润色，否则退超。"""
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(104)
    charged = await charge_generation(
        db_session, 104, model_code=None, enable_polish=True, ref_key="task-104"
    )
    assert await refund_generation(db_session, 104, ref_key="task-104") == charged
    assert await refund_polish_surcharge(db_session, 104, ref_key="task-104") == 0


@pytest.mark.asyncio
async def test_full_refund_after_polish_refund_pays_only_remainder(db_session):
    """先退了润色，再整单退款时只退剩余部分——累计不超过原扣费。"""
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(105)
    before = (await svc.get_or_create_quota(105)).credit_total

    # 3 章批量：每章都收了润色附加费
    charged = await charge_generation(
        db_session, 105, model_code=None, enable_polish=True, ref_key="task-105", chapters=3
    )
    assert charged == POLISH_PRICE * 3

    # 其中 1 章润色没兑现
    assert await refund_polish_surcharge(db_session, 105, ref_key="task-105", chapters=1) == POLISH_PRICE
    # 随后整单退款只补剩下的 2 份
    assert await refund_generation(db_session, 105, ref_key="task-105") == POLISH_PRICE * 2
    assert (await svc.get_or_create_quota(105)).credit_total == before


@pytest.mark.asyncio
async def test_batch_refund_counts_unpolished_chapters(db_session):
    """批量整批一笔扣费：按未兑现的章数退，不是一律退一份。"""
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(106)
    await charge_generation(
        db_session, 106, model_code=None, enable_polish=True, ref_key="task-106", chapters=4
    )
    assert await refund_polish_surcharge(
        db_session, 106, ref_key="task-106", chapters=3
    ) == POLISH_PRICE * 3


@pytest.mark.asyncio
async def test_polish_refund_capped_by_original_charge(db_session):
    """章数传得离谱也不能退超原扣费（防止把模型费一起退掉）。"""
    svc = QuotaService(db_session)
    await svc.get_or_create_quota(107)
    before = (await svc.get_or_create_quota(107)).credit_total
    charged = await charge_generation(
        db_session, 107, model_code=None, enable_polish=True, ref_key="task-107", chapters=2
    )

    refunded = await refund_polish_surcharge(db_session, 107, ref_key="task-107", chapters=99)
    assert refunded == charged
    assert (await svc.get_or_create_quota(107)).credit_total == before


@pytest.mark.asyncio
async def test_polish_refund_uses_price_at_charge_time(db_session):
    """管理员事后改价不影响已发生的扣费：退款按当时写进流水的单价回退。"""
    from app.models.system_config import SystemConfig

    svc = QuotaService(db_session)
    await svc.get_or_create_quota(108)
    await svc.add_purchased_credits(108, 500, ref_key="topup108")

    price = SystemConfig(key="credits.price.polish", value="20")
    db_session.add(price)
    await db_session.commit()

    charged = await charge_generation(
        db_session, 108, model_code=None, enable_polish=True, ref_key="task-108"
    )
    assert charged == 20

    price.value = "3"  # 事后降价
    await db_session.commit()
    assert await refund_polish_surcharge(db_session, 108, ref_key="task-108") == 20


@pytest.mark.asyncio
async def test_no_refund_without_ref_key(db_session):
    assert await refund_polish_surcharge(db_session, 109, ref_key=None) == 0
