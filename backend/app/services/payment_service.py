import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.payment_order import PaymentOrder
from ..models.plan import Plan
from ..repositories.system_config_repository import SystemConfigRepository

logger = logging.getLogger(__name__)


class PaymentService:
    """统一支付服务：支持支付宝、微信支付下单/回调验证/订单管理。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.config_repo = SystemConfigRepository(session)

    # ------------------------------------------------------------------
    # 配置读取
    # ------------------------------------------------------------------

    async def _get_config(self, key: str) -> Optional[str]:
        record = await self.config_repo.get_by_key(key)
        return record.value if record else None

    async def _get_alipay_config(self) -> Dict[str, str]:
        keys = [
            "pay.alipay.enabled", "pay.alipay.app_id",
            "pay.alipay.private_key", "pay.alipay.alipay_public_key",
            "pay.alipay.notify_url", "pay.alipay.mode",
        ]
        cfg: Dict[str, str] = {}
        for k in keys:
            short = k.replace("pay.alipay.", "")
            cfg[short] = (await self._get_config(k)) or ""
        return cfg

    async def _get_wechat_config(self) -> Dict[str, str]:
        keys = [
            "pay.wechat.enabled", "pay.wechat.mch_id", "pay.wechat.app_id",
            "pay.wechat.api_v3_key", "pay.wechat.serial_no",
            "pay.wechat.private_key", "pay.wechat.notify_url",
        ]
        cfg: Dict[str, str] = {}
        for k in keys:
            short = k.replace("pay.wechat.", "")
            cfg[short] = (await self._get_config(k)) or ""
        return cfg

    # ------------------------------------------------------------------
    # 支付宝
    # ------------------------------------------------------------------

    def _build_alipay_client(self, cfg: Dict[str, str]):
        """构建 python-alipay-sdk 客户端实例。"""
        from alipay import AliPay

        is_sandbox = cfg.get("mode") == "sandbox"
        return AliPay(
            appid=cfg["app_id"],
            app_notify_url=cfg.get("notify_url") or None,
            app_private_key_string=cfg["private_key"],
            alipay_public_key_string=cfg["alipay_public_key"],
            sign_type="RSA2",
            debug=is_sandbox,
        )

    async def create_alipay_order(
        self,
        *,
        user_id: int,
        plan_id: int,
        plan_name: str,
        amount: float,
        return_url: Optional[str] = None,
    ) -> PaymentOrder:
        cfg = await self._get_alipay_config()
        if cfg.get("enabled") != "true":
            raise ValueError("支付宝渠道未启用")
        if not cfg.get("app_id") or not cfg.get("private_key"):
            raise ValueError("支付宝配置不完整，请在管理后台填写 App ID 和私钥")

        client = self._build_alipay_client(cfg)
        order_no = f"AP{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:16].upper()}"

        order_string = client.api_alipay_trade_page_pay(
            out_trade_no=order_no,
            total_amount=str(round(float(amount), 2)),
            subject=f"Arboris - {plan_name}",
            return_url=return_url,
            notify_url=cfg.get("notify_url") or None,
        )

        gateway = "https://openapi.alipaydev.com/gateway.do" if cfg.get("mode") == "sandbox" else "https://openapi.alipay.com/gateway.do"
        pay_url = f"{gateway}?{order_string}"

        order = PaymentOrder(
            order_no=order_no,
            user_id=user_id,
            plan_id=plan_id,
            plan_name=plan_name,
            amount=amount,
            currency="CNY",
            channel="alipay",
            status="pending",
            pay_url=pay_url,
        )
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        logger.info("支付宝订单已创建: order_no=%s user=%s amount=%.2f", order_no, user_id, amount)
        return order

    async def _activate_membership(self, order: PaymentOrder) -> None:
        """支付成功后激活会员配额。"""
        from .quota_service import QuotaService

        plan_result = await self.session.execute(
            select(Plan).where(Plan.id == order.plan_id)
        )
        plan = plan_result.scalar_one_or_none()

        # 根据套餐周期计算到期时间
        expires_at = None
        if plan and plan.period == "monthly":
            expires_at = datetime.now() + timedelta(days=30)
        elif plan and plan.period == "yearly":
            expires_at = datetime.now() + timedelta(days=365)
        # period == "forever" 时 expires_at 保持 None

        quota_svc = QuotaService(self.session)
        await quota_svc.upgrade_to_premium(order.user_id, expires_at, plan=plan)
        logger.info("会员已激活: user_id=%s plan=%s expires_at=%s",
                     order.user_id, getattr(plan, 'name', None), expires_at)

    async def verify_alipay_callback(self, data: Dict[str, str]) -> Optional[PaymentOrder]:
        """验证支付宝异步回调签名并更新订单状态。成功返回订单，失败返回 None。"""
        cfg = await self._get_alipay_config()
        client = self._build_alipay_client(cfg)

        signature = data.pop("sign", "")
        sign_type = data.pop("sign_type", "RSA2")
        success = client.verify(data, signature)
        if not success:
            logger.warning("支付宝回调签名验证失败: data=%s", data)
            return None

        trade_status = data.get("trade_status", "")
        out_trade_no = data.get("out_trade_no", "")
        trade_no = data.get("trade_no", "")

        result = await self.session.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == out_trade_no)
        )
        order = result.scalar_one_or_none()
        if not order:
            logger.warning("支付宝回调订单不存在: out_trade_no=%s", out_trade_no)
            return None

        # 幂等性保护：订单已处理则直接返回（防止重复回调）
        if order.status != "pending":
            logger.info("支付宝回调但订单已处理（幂等性保护）: order_no=%s status=%s", out_trade_no, order.status)
            return order

        if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            # 校验回调金额与订单金额是否一致
            callback_amount = data.get("total_amount", "")
            try:
                if abs(float(callback_amount) - float(order.amount)) > 0.01:
                    logger.error("支付宝回调金额不匹配: order_no=%s 订单=%.2f 回调=%s",
                                 out_trade_no, float(order.amount), callback_amount)
                    return None
            except (ValueError, TypeError):
                logger.error("支付宝回调金额解析失败: order_no=%s total_amount=%s", out_trade_no, callback_amount)
                return None

            # 再次检查状态（防止并发回调）
            await self.session.refresh(order)
            if order.status != "pending":
                logger.warning("支付宝回调并发检测：订单已被处理: order_no=%s status=%s", out_trade_no, order.status)
                return order

            order.status = "paid"
            order.transaction_id = trade_no
            order.paid_at = datetime.now()
            await self.session.flush()
            await self._activate_membership(order)
            logger.info("支付宝支付成功: order_no=%s trade_no=%s", out_trade_no, trade_no)
        elif trade_status == "TRADE_CLOSED":
            order.status = "cancelled"
            logger.info("支付宝交易关闭: order_no=%s", out_trade_no)

        await self.session.commit()
        return order

    # ------------------------------------------------------------------
    # Stripe（Checkout Session，httpx 直连 REST，不引入 stripe SDK）
    # ------------------------------------------------------------------

    async def _get_stripe_config(self) -> Dict[str, str]:
        keys = [
            "pay.stripe.enabled", "pay.stripe.secret_key", "pay.stripe.webhook_secret",
            "pay.stripe.currency", "pay.stripe.success_url", "pay.stripe.cancel_url",
            "pay.stripe.mode",
        ]
        cfg: Dict[str, str] = {}
        for k in keys:
            cfg[k.replace("pay.stripe.", "")] = (await self._get_config(k)) or ""
        return cfg

    async def create_stripe_order(
        self,
        *,
        user_id: int,
        plan_id: int,
        plan_name: str,
        amount: float,
        return_url: Optional[str] = None,
    ) -> PaymentOrder:
        cfg = await self._get_stripe_config()
        if cfg.get("enabled") != "true":
            raise ValueError("Stripe 渠道未启用")
        secret_key = cfg.get("secret_key")
        if not secret_key:
            raise ValueError("Stripe 配置不完整，请在管理后台填写 Secret Key")

        currency = (cfg.get("currency") or "usd").lower()
        success_url = cfg.get("success_url") or return_url
        cancel_url = cfg.get("cancel_url") or return_url
        if not success_url or not cancel_url:
            raise ValueError("Stripe 配置不完整，请配置 success_url / cancel_url（或在下单时传 return_url）")

        order_no = f"ST{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:16].upper()}"
        # Stripe 金额以最小货币单位计（如分）；零小数币种(jpy 等)不乘 100
        zero_decimal = {"jpy", "krw", "vnd", "clp"}
        unit_amount = int(round(float(amount))) if currency in zero_decimal else int(round(float(amount) * 100))

        form = {
            "mode": "payment",
            "client_reference_id": order_no,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata[order_no]": order_no,
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": currency,
            "line_items[0][price_data][unit_amount]": str(unit_amount),
            "line_items[0][price_data][product_data][name]": f"Arboris - {plan_name}",
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.stripe.com/v1/checkout/sessions",
                    data=form,
                    headers={"Authorization": f"Bearer {secret_key}"},
                )
                data = resp.json()
        except Exception as exc:
            logger.warning("Stripe 创建会话异常: %s", exc)
            raise ValueError("Stripe 下单失败，请稍后重试")

        if resp.status_code >= 400 or not data.get("url"):
            msg = (data.get("error") or {}).get("message") or "未知错误"
            logger.warning("Stripe 创建会话失败: %s", msg)
            raise ValueError(f"Stripe 下单失败: {msg}")

        order = PaymentOrder(
            order_no=order_no,
            user_id=user_id,
            plan_id=plan_id,
            plan_name=plan_name,
            amount=amount,
            currency=currency.upper(),
            channel="stripe",
            status="pending",
            transaction_id=data.get("id"),  # Stripe checkout session id
            pay_url=data.get("url"),
        )
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        logger.info("Stripe 订单已创建: order_no=%s session=%s user=%s", order_no, data.get("id"), user_id)
        return order

    async def verify_stripe_webhook(self, payload: bytes, sig_header: str) -> Optional[PaymentOrder]:
        """验证 Stripe webhook 签名并在支付完成时激活会员。"""
        cfg = await self._get_stripe_config()
        webhook_secret = cfg.get("webhook_secret")
        if not webhook_secret:
            logger.error("未配置 Stripe webhook_secret，拒绝处理回调")
            raise PermissionError("stripe webhook 未配置")

        # 解析 Stripe-Signature: t=...,v1=...
        parts = dict(
            kv.split("=", 1) for kv in (sig_header or "").split(",") if "=" in kv
        )
        ts = parts.get("t")
        v1 = parts.get("v1")
        if not ts or not v1:
            logger.warning("Stripe webhook 签名头格式错误")
            raise PermissionError("stripe 签名头无效")
        # 时间戳容差 5 分钟，防重放
        try:
            if abs(time.time() - int(ts)) > 300:
                logger.warning("Stripe webhook 时间戳超出容差")
                raise PermissionError("stripe 时间戳超差")
        except ValueError:
            raise PermissionError("stripe 时间戳无效")

        signed_payload = f"{ts}.".encode("utf-8") + payload
        expected = hmac.new(webhook_secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, v1):
            logger.warning("Stripe webhook 签名验证失败")
            raise PermissionError("stripe 签名不匹配")

        try:
            event = json.loads(payload.decode("utf-8"))
        except Exception:
            logger.warning("Stripe webhook payload 解析失败")
            return None

        if event.get("type") != "checkout.session.completed":
            logger.info("Stripe webhook 忽略事件类型: %s", event.get("type"))
            return None

        sess = (event.get("data") or {}).get("object") or {}
        order_no = sess.get("client_reference_id") or (sess.get("metadata") or {}).get("order_no")
        # 仅当明确 payment_status == "paid" 才激活（缺失/null/unpaid 一律拒绝，防止误激活）
        if sess.get("payment_status") != "paid":
            logger.info("Stripe 会话未支付完成: order_no=%s status=%s", order_no, sess.get("payment_status"))
            return None

        result = await self.session.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == order_no)
        )
        order = result.scalar_one_or_none()
        if not order:
            logger.warning("Stripe webhook 订单不存在: order_no=%s", order_no)
            return None
        if order.status != "pending":  # 幂等
            logger.info("Stripe webhook 订单已处理（幂等）: order_no=%s status=%s", order_no, order.status)
            return order

        order.status = "paid"
        order.transaction_id = sess.get("payment_intent") or sess.get("id") or order.transaction_id
        order.paid_at = datetime.now()
        await self.session.flush()
        await self._activate_membership(order)
        await self.session.commit()
        logger.info("Stripe 支付成功并激活会员: order_no=%s", order_no)
        return order

    # ------------------------------------------------------------------
    # 微信支付
    # ------------------------------------------------------------------

    def _build_wechat_client(self, cfg: Dict[str, str]):
        """构建 wechatpayv3 客户端实例。"""
        from wechatpayv3 import WeChatPay, WeChatPayType

        return WeChatPay(
            wechatpay_type=WeChatPayType.NATIVE,
            mchid=cfg["mch_id"],
            private_key=cfg["private_key"],
            cert_serial_no=cfg["serial_no"],
            apiv3_key=cfg["api_v3_key"],
            appid=cfg["app_id"],
            notify_url=cfg.get("notify_url") or None,
        )

    async def create_wechat_order(
        self,
        *,
        user_id: int,
        plan_id: int,
        plan_name: str,
        amount: float,
    ) -> PaymentOrder:
        cfg = await self._get_wechat_config()
        if cfg.get("enabled") != "true":
            raise ValueError("微信支付渠道未启用")
        if not cfg.get("mch_id") or not cfg.get("private_key"):
            raise ValueError("微信支付配置不完整，请在管理后台填写商户号和私钥")

        client = self._build_wechat_client(cfg)
        order_no = f"WX{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:16].upper()}"

        # 微信支付金额单位为分
        total_fen = int(round(amount * 100))
        code, message_resp = client.pay(
            description=f"Arboris - {plan_name}",
            out_trade_no=order_no,
            amount={"total": total_fen, "currency": "CNY"},
            notify_url=cfg.get("notify_url") or None,
        )

        pay_url = None
        if isinstance(message_resp, dict):
            pay_url = message_resp.get("code_url")
        elif isinstance(message_resp, str):
            import json
            try:
                resp_data = json.loads(message_resp)
                pay_url = resp_data.get("code_url")
            except (json.JSONDecodeError, AttributeError):
                pass

        if not pay_url:
            logger.error("微信支付下单失败: code=%s resp=%s", code, message_resp)
            raise ValueError(f"微信支付下单失败: {message_resp}")

        order = PaymentOrder(
            order_no=order_no,
            user_id=user_id,
            plan_id=plan_id,
            plan_name=plan_name,
            amount=amount,
            currency="CNY",
            channel="wechat",
            status="pending",
            pay_url=pay_url,
        )
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        logger.info("微信支付订单已创建: order_no=%s user=%s amount=%.2f code_url=%s", order_no, user_id, amount, pay_url[:30])
        return order

    async def verify_wechat_callback(
        self, headers: Dict[str, str], body: str
    ) -> Optional[PaymentOrder]:
        """验证微信支付异步回调并更新订单状态。"""
        cfg = await self._get_wechat_config()
        client = self._build_wechat_client(cfg)

        try:
            result = client.callback(headers, body)
        except Exception as exc:
            logger.warning("微信支付回调验证失败: %s", exc)
            return None

        if not result or not isinstance(result, dict):
            logger.warning("微信支付回调解密失败")
            return None

        out_trade_no = result.get("out_trade_no", "")
        transaction_id = result.get("transaction_id", "")
        trade_state = result.get("trade_state", "")

        db_result = await self.session.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == out_trade_no)
        )
        order = db_result.scalar_one_or_none()
        if not order:
            logger.warning("微信支付回调订单不存在: out_trade_no=%s", out_trade_no)
            return None

        # 幂等性保护：订单已处理则直接返回（防止重复回调）
        if order.status != "pending":
            logger.info("微信支付回调但订单已处理（幂等性保护）: order_no=%s status=%s", out_trade_no, order.status)
            return order

        if trade_state == "SUCCESS":
            # 校验回调金额与订单金额是否一致（微信金额单位为分）
            callback_amount = result.get("amount", {})
            callback_total = callback_amount.get("total", 0) if isinstance(callback_amount, dict) else 0
            expected_fen = int(round(float(order.amount) * 100))
            if callback_total != expected_fen:
                logger.error("微信回调金额不匹配: order_no=%s 订单=%d分 回调=%d分",
                             out_trade_no, expected_fen, callback_total)
                return None

            # 再次检查状态（防止并发回调）
            await self.session.refresh(order)
            if order.status != "pending":
                logger.warning("微信支付回调并发检测：订单已被处理: order_no=%s status=%s", out_trade_no, order.status)
                return order

            order.status = "paid"
            order.transaction_id = transaction_id
            order.paid_at = datetime.now()
            await self.session.flush()
            await self._activate_membership(order)
            logger.info("微信支付成功: order_no=%s transaction_id=%s", out_trade_no, transaction_id)
        elif trade_state in ("CLOSED", "REVOKED", "PAYERROR"):
            order.status = "cancelled"
            logger.info("微信支付交易关闭: order_no=%s state=%s", out_trade_no, trade_state)

        await self.session.commit()
        return order

    # ------------------------------------------------------------------
    # 订单查询
    # ------------------------------------------------------------------

    async def get_order_by_no(self, order_no: str) -> Optional[PaymentOrder]:
        result = await self.session.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == order_no)
        )
        return result.scalar_one_or_none()

    async def list_orders(
        self,
        *,
        user_id: Optional[int] = None,
        channel: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[PaymentOrder], int]:
        """分页查询订单，管理员可不传 user_id 查全部。"""
        stmt = select(PaymentOrder)
        count_stmt = select(func.count(PaymentOrder.id))

        if user_id is not None:
            stmt = stmt.where(PaymentOrder.user_id == user_id)
            count_stmt = count_stmt.where(PaymentOrder.user_id == user_id)
        if channel:
            stmt = stmt.where(PaymentOrder.channel == channel)
            count_stmt = count_stmt.where(PaymentOrder.channel == channel)
        if status:
            stmt = stmt.where(PaymentOrder.status == status)
            count_stmt = count_stmt.where(PaymentOrder.status == status)

        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.order_by(desc(PaymentOrder.created_at)).offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(stmt)).scalars().all()
        return list(rows), total

    async def list_orders_for_admin(
        self,
        *,
        channel: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """管理员查询所有订单，附带用户名信息。"""
        from ..models import User

        stmt = (
            select(PaymentOrder, User.username)
            .outerjoin(User, PaymentOrder.user_id == User.id)
        )
        count_stmt = select(func.count(PaymentOrder.id))

        if channel:
            stmt = stmt.where(PaymentOrder.channel == channel)
            count_stmt = count_stmt.where(PaymentOrder.channel == channel)
        if status:
            stmt = stmt.where(PaymentOrder.status == status)
            count_stmt = count_stmt.where(PaymentOrder.status == status)

        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.order_by(desc(PaymentOrder.created_at)).offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(stmt)).all()

        result = []
        for order, username in rows:
            result.append({
                "id": order.id,
                "order_no": order.order_no,
                "username": username or f"user_{order.user_id}",
                "user_id": order.user_id,
                "plan_id": order.plan_id,
                "plan_name": order.plan_name,
                "amount": order.amount,
                "currency": order.currency,
                "channel": order.channel,
                "status": order.status,
                "transaction_id": order.transaction_id,
                "paid_at": order.paid_at.isoformat() if order.paid_at else None,
                "refunded_at": order.refunded_at.isoformat() if order.refunded_at else None,
                "remark": order.remark,
                "created_at": order.created_at.isoformat() if order.created_at else None,
            })
        return result, total
