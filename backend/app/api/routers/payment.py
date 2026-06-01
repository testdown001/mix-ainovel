import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_admin, get_current_user
from ...db.session import get_session
from ...schemas.user import UserInDB
from ...services.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payment", tags=["Payment"])


def get_payment_service(session: AsyncSession = Depends(get_session)) -> PaymentService:
    return PaymentService(session)


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class CreateOrderRequest(BaseModel):
    plan_id: int
    channel: str  # alipay | wechat
    return_url: Optional[str] = None


class CreateOrderResponse(BaseModel):
    order_no: str
    pay_url: Optional[str] = None
    channel: str
    status: str


class OrderItem(BaseModel):
    id: int
    order_no: str
    username: Optional[str] = None
    user_id: int
    plan_id: int
    plan_name: str
    amount: float
    currency: str
    channel: str
    status: str
    transaction_id: Optional[str] = None
    paid_at: Optional[str] = None
    refunded_at: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[str] = None


class OrderListResponse(BaseModel):
    items: list[OrderItem]
    total: int
    page: int
    page_size: int


# ------------------------------------------------------------------
# 用户下单
# ------------------------------------------------------------------

@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order(
    payload: CreateOrderRequest,
    current_user: UserInDB = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """创建支付订单（支付宝 / 微信支付）。"""
    from ...models.plan import Plan
    from sqlalchemy import select

    result = await service.session.execute(select(Plan).where(Plan.id == payload.plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")
    if not plan.is_active:
        raise HTTPException(status_code=400, detail="该套餐已下架")

    try:
        if payload.channel == "alipay":
            order = await service.create_alipay_order(
                user_id=current_user.id,
                plan_id=plan.id,
                plan_name=plan.name,
                amount=plan.price,
                return_url=payload.return_url,
            )
        elif payload.channel == "wechat":
            order = await service.create_wechat_order(
                user_id=current_user.id,
                plan_id=plan.id,
                plan_name=plan.name,
                amount=plan.price,
            )
        elif payload.channel == "stripe":
            order = await service.create_stripe_order(
                user_id=current_user.id,
                plan_id=plan.id,
                plan_name=plan.name,
                amount=plan.price,
                return_url=payload.return_url,
            )
        else:
            raise HTTPException(status_code=400, detail=f"不支持的支付渠道: {payload.channel}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CreateOrderResponse(
        order_no=order.order_no,
        pay_url=order.pay_url,
        channel=order.channel,
        status=order.status,
    )


# ------------------------------------------------------------------
# 支付宝异步回调
# ------------------------------------------------------------------

@router.post("/alipay/notify")
async def alipay_notify(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """支付宝异步回调通知。验证签名后更新订单状态，返回 'success' 表示已处理。"""
    form_data = await request.form()
    data = {k: v for k, v in form_data.items()}
    logger.info("收到支付宝回调: out_trade_no=%s trade_status=%s", data.get("out_trade_no"), data.get("trade_status"))

    service = PaymentService(session)
    order = await service.verify_alipay_callback(data)
    if order:
        return PlainTextResponse("success")
    return PlainTextResponse("fail")


# ------------------------------------------------------------------
# 微信支付异步回调
# ------------------------------------------------------------------

@router.post("/wechat/notify")
async def wechat_notify(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """微信支付异步回调通知。验证签名后更新订单状态。"""
    body = (await request.body()).decode("utf-8")
    headers = {
        "Wechatpay-Signature": request.headers.get("Wechatpay-Signature", ""),
        "Wechatpay-Timestamp": request.headers.get("Wechatpay-Timestamp", ""),
        "Wechatpay-Nonce": request.headers.get("Wechatpay-Nonce", ""),
        "Wechatpay-Serial": request.headers.get("Wechatpay-Serial", ""),
    }
    logger.info("收到微信支付回调: body_len=%d", len(body))

    service = PaymentService(session)
    order = await service.verify_wechat_callback(headers, body)
    if order:
        return {"code": "SUCCESS", "message": "OK"}
    return PlainTextResponse('{"code":"FAIL","message":"签名验证失败"}', status_code=400)


# ------------------------------------------------------------------
# Stripe webhook 回调（checkout.session.completed → 激活会员）
# ------------------------------------------------------------------

@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Stripe 异步回调。验证 Stripe-Signature 后在支付完成时激活会员。"""
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")
    logger.info("收到 Stripe webhook: body_len=%d", len(payload))

    service = PaymentService(session)
    try:
        await service.verify_stripe_webhook(payload, sig_header)
    except PermissionError:
        # 仅签名/校验失败返回 400（拒收）；其余"签名通过但无需动作"返回 200，避免 Stripe 无限重试
        return PlainTextResponse('{"received": false}', status_code=400)
    return {"received": True}


# ------------------------------------------------------------------
# 用户订单查询
# ------------------------------------------------------------------

@router.get("/orders")
async def list_my_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserInDB = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """查询当前用户的支付订单。"""
    orders, total = await service.list_orders(
        user_id=current_user.id, page=page, page_size=page_size
    )
    return {
        "items": [
            {
                "id": o.id,
                "order_no": o.order_no,
                "plan_name": o.plan_name,
                "amount": o.amount,
                "channel": o.channel,
                "status": o.status,
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/orders/{order_no}/status")
async def get_order_status(
    order_no: str,
    current_user: UserInDB = Depends(get_current_user),
    service: PaymentService = Depends(get_payment_service),
):
    """查询订单支付状态。"""
    order = await service.get_order_by_no(order_no)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {
        "order_no": order.order_no,
        "status": order.status,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    }


# ------------------------------------------------------------------
# 管理员订单查询
# ------------------------------------------------------------------

@router.get("/admin/orders")
async def admin_list_orders(
    channel: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: UserInDB = Depends(get_current_admin),
    service: PaymentService = Depends(get_payment_service),
):
    """管理员查询所有支付订单。"""
    items, total = await service.list_orders_for_admin(
        channel=channel, status=status, page=page, page_size=page_size
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
