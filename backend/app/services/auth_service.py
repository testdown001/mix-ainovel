# AIMETA P=认证服务_登录注册业务逻辑|R=登录_注册_令牌|NR=不含用户管理|E=AuthService|X=internal|A=服务类|D=jose,passlib|S=db|RD=./README.ai
import asyncio
import logging
import random
import re
import secrets
import string
import time
from typing import Dict, Optional

import httpx
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr
from fastapi import HTTPException, status

import smtplib
import redis.asyncio as aioredis

from ..core.config import settings
from ..core.security import create_access_token, hash_password, verify_password
from ..models import User
from ..repositories.system_config_repository import SystemConfigRepository
from ..repositories.user_repository import UserRepository
from ..schemas.user import AuthOptions, Token, UserCreate, UserInDB, UserRegistration


# 向后兼容：内存缓存作为 Redis 不可用时的降级方案
_VERIFICATION_CACHE: Dict[str, tuple[str, float]] = {}
_LAST_SEND_TIME: Dict[str, float] = {}


class AuthService:
    """认证与授权逻辑，封装登录、注册、OAuth 对接等操作。"""

    def __init__(self, session):
        self.session = session
        self.user_repo = UserRepository(session)
        self.system_config_repo = SystemConfigRepository(session)
        self._verification_cache = _VERIFICATION_CACHE
        self._last_send_time = _LAST_SEND_TIME
        self._redis = None
        self._logger = logging.getLogger(__name__)

    async def _get_redis(self):
        """获取 Redis 连接（懒加载）"""
        if self._redis is None:
            try:
                self._redis = await aioredis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                )
                # 测试连接
                await self._redis.ping()
            except Exception as e:
                self._logger.warning("Redis 连接失败，降级到内存缓存: %s", e)
                self._redis = None
        return self._redis

    # ------------------------------------------------------------------
    # 用户登录 / 注册
    # ------------------------------------------------------------------

    async def authenticate_user(self, username: str, password: str) -> User:
        user = await self.user_repo.get_by_username(username)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员")
        return user

    async def create_access_token(
        self,
        user: User | UserInDB,
        *,
        must_change_password: Optional[bool] = None,
    ) -> Token:
        # username/is_premium 供 Go 网关识别用户并选择正确的限流档位
        from .quota_service import QuotaService
        quota = await QuotaService(self.session).get_quota(user.id)
        payload = {
            "is_admin": user.is_admin,
            "username": user.username,
            "is_premium": bool(quota and quota.is_premium_active),
        }
        token = create_access_token(user.id, extra_claims=payload)
        should_change = self.requires_password_reset(user) if must_change_password is None else must_change_password
        return Token(access_token=token, must_change_password=should_change)

    async def register_user(self, payload: UserRegistration) -> User:
        if not await self.is_registration_enabled():
            raise HTTPException(status_code=403, detail="当前暂未开放注册")

        captcha_enabled = self._parse_bool(
            await self._get_config_value("captcha.enabled"), False
        )
        if captcha_enabled:
            if not payload.captcha_token:
                raise HTTPException(status_code=400, detail="请完成人机验证")
            secret_key = await self._get_config_value("captcha.secret_key")
            if not await self._verify_turnstile(payload.captcha_token, secret_key):
                raise HTTPException(status_code=400, detail="人机验证失败，请重试")

        if await self.user_repo.get_by_username(payload.username):
            raise HTTPException(status_code=400, detail="用户名已存在")
        if payload.email and await self.user_repo.get_by_email(payload.email):
            raise HTTPException(status_code=400, detail="邮箱已被使用")

        if not await self.verify_code(payload.email, payload.verification_code):
            raise HTTPException(status_code=400, detail="验证码错误或已过期")

        hashed_password = hash_password(payload.password)
        user = User(
            username=payload.username,
            email=payload.email,
            hashed_password=hashed_password,
        )
        self.session.add(user)
        await self.session.commit()
        return user

    # ------------------------------------------------------------------
    # 邮箱验证码逻辑
    # ------------------------------------------------------------------

    async def send_verification_code(self, email: str, purpose: str = "register") -> None:
        """发送验证码邮件。

        Args:
            email: 目标邮箱
            purpose: 验证码用途，'register' 或 'reset'
        """
        if purpose == "register":
            if not await self.is_registration_enabled():
                raise HTTPException(status_code=403, detail="当前暂未开放注册")
        elif purpose == "reset":
            # 密码重置：验证用户存在（防止邮箱枚举，静默失败）
            user = await self.user_repo.get_by_email(email)
            if not user:
                # 不抛出异常，防止邮箱枚举攻击
                return

        cache_key = f"{purpose}:{email}"
        rate_limit_key = f"rate_limit:{cache_key}"
        now = time.time()

        # 尝试使用 Redis
        redis = await self._get_redis()
        if redis:
            try:
                # 检查发送频率限制
                last_send = await redis.get(rate_limit_key)
                if last_send and now - float(last_send) < 60:
                    raise HTTPException(status_code=429, detail="请稍后再试，1分钟内不可重复发送")

                # 生成验证码
                code = "".join(random.choices(string.digits, k=6))

                # 存储到 Redis（5分钟过期）
                await redis.setex(f"verify_code:{cache_key}", 300, code)
                await redis.setex(rate_limit_key, 60, str(now))

                self._logger.info("验证码已存储到 Redis: %s", cache_key)
            except Exception as e:
                self._logger.error("Redis 操作失败，降级到内存缓存: %s", e)
                redis = None

        # 降级到内存缓存
        if redis is None:
            if cache_key in self._last_send_time and now - self._last_send_time[cache_key] < 60:
                raise HTTPException(status_code=429, detail="请稍后再试，1分钟内不可重复发送")

            code = "".join(random.choices(string.digits, k=6))
            self._verification_cache[cache_key] = (code, now + 300)
            self._last_send_time[cache_key] = now
            self._logger.warning("使用内存缓存存储验证码: %s", cache_key)

        smtp_config = await self._load_smtp_config()
        if not smtp_config:
            raise HTTPException(status_code=500, detail="未配置邮件服务，请联系管理员")

        await self._send_email(email, code, smtp_config, purpose)

    async def verify_code(self, email: str | None, code: str, purpose: str = "register") -> bool:
        """验证验证码。

        Args:
            email: 邮箱
            code: 验证码
            purpose: 验证码用途，'register' 或 'reset'
        """
        if not email:
            return False

        cache_key = f"{purpose}:{email}"

        # 尝试从 Redis 验证
        redis = await self._get_redis()
        if redis:
            try:
                stored_code = await redis.get(f"verify_code:{cache_key}")
                if stored_code and stored_code == code:
                    # 验证成功，删除验证码
                    await redis.delete(f"verify_code:{cache_key}")
                    self._logger.info("验证码验证成功（Redis）: %s", cache_key)
                    return True
                return False
            except Exception as e:
                self._logger.error("Redis 验证失败，降级到内存缓存: %s", e)
                redis = None

        # 降级到内存缓存
        if redis is None:
            cached = self._verification_cache.get(cache_key)
            if not cached:
                return False
            expected, expire_at = cached
            if time.time() > expire_at:
                self._verification_cache.pop(cache_key, None)
                return False
            if code != expected:
                return False
            self._verification_cache.pop(cache_key, None)
            self._logger.info("验证码验证成功（内存）: %s", cache_key)
            return True

        return False

    # ==================== 手机号登录（验证码登录即注册）====================

    _PHONE_RE = re.compile(r"^1[3-9]\d{9}$")

    @classmethod
    def _normalize_phone(cls, phone: str) -> str:
        return (phone or "").strip().replace(" ", "")

    async def is_phone_login_enabled(self) -> bool:
        return self._parse_bool(await self._get_config_value("auth.phone_enabled"), False)

    async def _generate_unique_username(self, base: str) -> str:
        """基于昵称/手机号生成不冲突的用户名。"""
        cleaned = re.sub(r"\s+", "", base or "").strip() or "用户"
        cleaned = cleaned[:40]
        candidate = cleaned
        for _ in range(6):
            if await self.user_repo.get_by_username(candidate) is None:
                return candidate
            candidate = f"{cleaned}_{secrets.token_hex(3)}"
        return f"u_{secrets.token_hex(6)}"

    async def send_phone_code(self, phone: str) -> None:
        """下发手机验证码（验证码登录即注册）。"""
        if not await self.is_phone_login_enabled():
            raise HTTPException(status_code=403, detail="未启用手机号登录")
        phone = self._normalize_phone(phone)
        if not self._PHONE_RE.match(phone):
            raise HTTPException(status_code=400, detail="手机号格式不正确")

        cache_key = f"phone_login:{phone}"
        rate_limit_key = f"rate_limit:{cache_key}"
        now = time.time()
        code = "".join(random.choices(string.digits, k=6))

        redis = await self._get_redis()
        if redis:
            try:
                last_send = await redis.get(rate_limit_key)
                if last_send and now - float(last_send) < 60:
                    raise HTTPException(status_code=429, detail="请稍后再试，1分钟内不可重复发送")
                await redis.setex(f"verify_code:{cache_key}", 300, code)
                await redis.setex(rate_limit_key, 60, str(now))
            except HTTPException:
                raise
            except Exception as exc:
                self._logger.error("Redis 操作失败，降级内存缓存: %s", exc)
                redis = None
        if redis is None:
            if cache_key in self._last_send_time and now - self._last_send_time[cache_key] < 60:
                raise HTTPException(status_code=429, detail="请稍后再试，1分钟内不可重复发送")
            self._verification_cache[cache_key] = (code, now + 300)
            self._last_send_time[cache_key] = now

        from .sms_service import SmsService

        sent = await SmsService(self.session).send_code(phone, code)
        if not sent:
            raise HTTPException(status_code=500, detail="短信发送失败，请检查短信服务配置或稍后重试")

    async def login_with_phone(self, phone: str, code: str) -> Token:
        """手机号 + 验证码登录；首次自动创建账号。"""
        if not await self.is_phone_login_enabled():
            raise HTTPException(status_code=403, detail="未启用手机号登录")
        phone = self._normalize_phone(phone)
        if not self._PHONE_RE.match(phone):
            raise HTTPException(status_code=400, detail="手机号格式不正确")
        if not await self.verify_code(phone, code, purpose="phone_login"):
            raise HTTPException(status_code=400, detail="验证码错误或已过期")

        user = await self.user_repo.get_by_phone(phone)
        if user is None:
            username = await self._generate_unique_username(f"手机用户{phone[-4:]}")
            user = User(
                username=username,
                phone=phone,
                hashed_password=hash_password(secrets.token_urlsafe(16)),
            )
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
        if not user.is_active:
            raise HTTPException(status_code=403, detail="账号已被禁用")
        return await self.create_access_token(user)

    # ==================== 微信 / 谷歌 OAuth ====================

    async def is_wechat_login_enabled(self) -> bool:
        return self._parse_bool(await self._get_config_value("auth.wechat_enabled"), False)

    async def is_google_login_enabled(self) -> bool:
        return self._parse_bool(await self._get_config_value("auth.google_enabled"), False)

    async def build_wechat_authorize_url(self) -> str:
        if not await self.is_wechat_login_enabled():
            raise HTTPException(status_code=404, detail="未启用微信登录")
        app_id = await self._get_config_value("wechat.app_id")
        redirect_uri = await self._get_config_value("wechat.redirect_uri")
        if not all([app_id, redirect_uri]):
            raise HTTPException(status_code=500, detail="未配置微信 OAuth 参数")
        from urllib.parse import quote
        # 网站应用扫码登录（开放平台）
        return (
            "https://open.weixin.qq.com/connect/qrconnect"
            f"?appid={app_id}&redirect_uri={quote(redirect_uri, safe='')}"
            "&response_type=code&scope=snsapi_login&state=arboris#wechat_redirect"
        )

    async def handle_wechat_callback(self, code: str) -> Token:
        if not await self.is_wechat_login_enabled():
            raise HTTPException(status_code=403, detail="未启用微信登录")
        app_id = await self._get_config_value("wechat.app_id")
        app_secret = await self._get_config_value("wechat.app_secret")
        if not all([app_id, app_secret]):
            raise HTTPException(status_code=500, detail="未配置微信 OAuth 参数")
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.get(
                "https://api.weixin.qq.com/sns/oauth2/access_token",
                params={"appid": app_id, "secret": app_secret, "code": code,
                        "grant_type": "authorization_code"},
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            openid = token_data.get("openid")
            if not access_token or not openid:
                raise HTTPException(status_code=400, detail=f"微信授权失败: {token_data.get('errmsg', '未知错误')}")
            info_resp = await client.get(
                "https://api.weixin.qq.com/sns/userinfo",
                params={"access_token": access_token, "openid": openid},
            )
            info = info_resp.json()
        unionid = info.get("unionid") or token_data.get("unionid")
        external_id = f"wechat:{unionid or openid}"
        nickname = info.get("nickname") or f"微信用户{openid[:6]}"
        return await self._login_or_create_oauth(external_id, nickname, email=None)

    async def handle_google_callback(self, code: str) -> Token:
        if not await self.is_google_login_enabled():
            raise HTTPException(status_code=403, detail="未启用谷歌登录")
        client_id = await self._get_config_value("google.client_id")
        client_secret = await self._get_config_value("google.client_secret")
        redirect_uri = await self._get_config_value("google.redirect_uri")
        if not all([client_id, client_secret, redirect_uri]):
            raise HTTPException(status_code=500, detail="未配置 Google OAuth 参数")
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={"code": code, "client_id": client_id, "client_secret": client_secret,
                      "redirect_uri": redirect_uri, "grant_type": "authorization_code"},
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="谷歌授权失败，未获取到访问令牌")
            info_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            info = info_resp.json()
        sub = info.get("sub")
        if not sub:
            raise HTTPException(status_code=400, detail="谷歌授权失败，未获取到用户标识")
        external_id = f"google:{sub}"
        name = info.get("name") or info.get("email") or f"google_{sub[:6]}"
        return await self._login_or_create_oauth(external_id, name, email=info.get("email"))

    async def _login_or_create_oauth(self, external_id: str, display_name: str, email: Optional[str]) -> Token:
        """OAuth 通用：按 external_id 找用户，无则建号；校验启用态后发令牌。"""
        user = await self.user_repo.get_by_external_id(external_id)
        if user is None:
            username = await self._generate_unique_username(display_name)
            safe_email = email if email and await self.user_repo.get_by_email(email) is None else None
            user = User(
                username=username,
                email=safe_email,
                external_id=external_id,
                hashed_password=hash_password(secrets.token_urlsafe(16)),
            )
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
        if not user.is_active:
            raise HTTPException(status_code=403, detail="账号已被禁用")
        return await self.create_access_token(user)

    async def _load_smtp_config(self) -> Optional[Dict[str, str]]:
        keys = [
            "smtp.server",
            "smtp.port",
            "smtp.username",
            "smtp.password",
            "smtp.from",
        ]
        configs = {}
        for key in keys:
            config = await self.system_config_repo.get_by_key(key)
            if config:
                configs[key] = config.value

        required_keys = {"smtp.server", "smtp.port", "smtp.username", "smtp.password", "smtp.from"}
        if not required_keys.issubset(configs.keys()):
            return None

        return configs

    async def _send_email(self, to_email: str, code: str, smtp_config: Dict[str, str], purpose: str = "register") -> None:
        """发送验证码邮件。

        Args:
            to_email: 收件人邮箱
            code: 验证码
            smtp_config: SMTP 配置
            purpose: 邮件用途，'register' 或 'reset'
        """
        logger = logging.getLogger(__name__)
        server = smtp_config["smtp.server"]
        port = int(smtp_config.get("smtp.port", "465"))
        username = smtp_config["smtp.username"]
        password = smtp_config["smtp.password"]
        from_value = smtp_config.get("smtp.from") or username
        display_name, from_addr = parseaddr(from_value)
        if not display_name and "@" not in from_value and "<" not in from_value and from_value.strip():
            display_name = from_value.strip()
        if not from_addr or "@" not in from_addr:
            if from_addr and "@" not in from_addr:
                logger.warning(
                    "发件邮箱缺少 @，已回退为登录账号",
                    extra={"original": from_addr},
                )
            from_addr = username
        try:
            from_addr.encode("ascii")
        except UnicodeEncodeError:
            logger.warning(
                "发件邮箱包含非 ASCII 字符，已回退为登录账号",
                extra={"original": from_addr},
            )
            from_addr = username
        if display_name:
            formatted_from = formataddr((Header(display_name, "utf-8").encode(), from_addr))
        else:
            formatted_from = from_addr

        try:
            to_email.encode("ascii")
        except UnicodeEncodeError as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="邮箱地址包含不支持的字符") from exc

        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta http-equiv=\"Content-Type\" content=\"text/html; charset=UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>您的验证码</title>
    <style>
        body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
        table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
        img {{ -ms-interpolation-mode: bicubic; }}
        body {{ margin: 0; padding: 0; }}
        table {{ border-collapse: collapse !important; }}
    </style>
</head>
<body style=\"margin: 0; padding: 0; width: 100% !important; background-color: #f3f4f6;\">
    <table width=\"100%\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" bgcolor=\"#f3f4f6\">
        <tr>
            <td align=\"center\" valign=\"top\" style=\"padding: 20px;\">
                <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"100%\" style=\"max-width: 512px; background-color: #ffffff; border-radius: 16px; overflow: hidden;\">
                    <tr>
                        <td align=\"center\" style=\"background-color: #2563eb; padding: 32px;\">
                            <h1 style=\"font-family: Arial, Helvetica, sans-serif; font-size: 30px; font-weight: bold; color: #ffffff; margin: 0;\">操作验证码</h1>
                            <p style=\"font-family: Arial, Helvetica, sans-serif; font-size: 16px; color: #dbeafe; margin: 8px 0 0;\">请使用下方验证码完成操作。</p>
                        </td>
                    </tr>
                    <tr>
                        <td align=\"center\" style=\"padding: 32px 48px;\">
                            <table border=\"0\" cellpadding=\"0\" cellspacing=\"0\" width=\"100%\">
                                <tr>
                                    <td align=\"center\" style=\"background-color: #f3f4f6; border-radius: 12px; padding: 16px; margin: 24px 0;\">
                                        <p style=\"font-family: 'Courier New', Courier, monospace; font-size: 48px; font-weight: bold; letter-spacing: 0.1em; color: #1d4ed8; margin: 0;\">
                                            {code[:3]}{code[3:]}
                                        </p>
                                    </td>
                                </tr>
                                <tr>
                                    <td align=\"center\" style=\"padding-top: 24px;\">
                                        <p style=\"font-family: Arial, Helvetica, sans-serif; font-size: 16px; color: #6b7280; margin: 0;\">
                                            此验证码将在 <span style=\"font-weight: bold; color: #374151;\">5分钟</span> 内有效。
                                        </p>
                                    </td>
                                </tr>
                                <tr>
                                    <td align=\"center\" style=\"padding-top: 32px; border-top: 1px solid #e5e7eb; margin-top: 32px;\">
                                        <p style=\"font-family: Arial, Helvetica, sans-serif; font-size: 14px; font-weight: bold; color: #ef4444; margin: 0;\">
                                            为保障安全，请勿泄露此验证码。
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td align=\"center\" style=\"background-color: #f9fafb; padding: 24px; border-top: 1px solid #e5e7eb;\">
                            <p style=\"font-family: Arial, Helvetica, sans-serif; font-size: 14px; color: #6b7280; margin: 0;\">
                                如非本人操作，请忽略此邮件。
                            </p>
                            <p style=\"font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #9ca3af; margin: 8px 0 0;\">
                                &copy; {time.strftime('%Y')} 拯救小说家. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        message = MIMEText(html_content, "html", "utf-8")
        message["Subject"] = Header("注册验证码", "utf-8").encode()
        message["From"] = formatted_from
        message["To"] = to_email

        logger.info("准备发送验证码邮件", extra={"to": to_email, "server": server, "port": port})

        def _send():
            smtp: Optional[smtplib.SMTP] = None
            try:
                if port == 465:
                    smtp = smtplib.SMTP_SSL(server, port, timeout=10)
                else:
                    smtp = smtplib.SMTP(server, port, timeout=10)
                    smtp.starttls()
                if username and password:
                    smtp.login(username, password)
                smtp.sendmail(from_addr, [to_email], message.as_string())
                logger.info("验证码邮件发送成功", extra={"to": to_email})
            except Exception as exc:  # noqa: BLE001
                logger.exception("验证码发送失败")
                raise
            finally:
                if smtp is not None:
                    try:
                        smtp.quit()
                    except Exception:  # noqa: BLE001
                        pass

        try:
            await asyncio.to_thread(_send)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail="验证码发送失败，请检查邮件配置") from exc

    # ------------------------------------------------------------------
    # OAuth 对接示例（以 Linux.do 为例）
    # ------------------------------------------------------------------

    async def handle_linuxdo_callback(self, code: str) -> Token:
        if not await self.is_linuxdo_login_enabled():
            raise HTTPException(status_code=403, detail="未启用 Linux.do 登录")
        client_id = await self._get_config_value("linuxdo.client_id")
        client_secret = await self._get_config_value("linuxdo.client_secret")
        redirect_uri = await self._get_config_value("linuxdo.redirect_uri")
        token_url = await self._get_config_value("linuxdo.token_url")
        user_info_url = await self._get_config_value("linuxdo.user_info_url")

        if not all([client_id, client_secret, redirect_uri, token_url, user_info_url]):
            raise HTTPException(status_code=500, detail="未正确配置 Linux.do OAuth 参数")

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                token_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="授权失败，未获取到访问令牌")

            user_info_response = await client.get(
                user_info_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_info_response.raise_for_status()
            data = user_info_response.json()

        external_id = f"linuxdo:{data['id']}"
        user = await self.user_repo.get_by_external_id(external_id)
        if user is None:
            placeholder_password = secrets.token_urlsafe(16)
            user = User(
                username=data["username"],
                email=data.get("email"),
                external_id=external_id,
                hashed_password=hash_password(placeholder_password),
            )
            self.session.add(user)
            await self.session.commit()
        elif not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员")

        return await self.create_access_token(user)

    async def _get_config_value(self, key: str) -> Optional[str]:
        config = await self.system_config_repo.get_by_key(key)
        return config.value if config else None

    async def get_config_value(self, key: str) -> Optional[str]:
        """对外暴露的配置读取接口，便于路由层复用。"""
        return await self._get_config_value(key)

    @staticmethod
    def _parse_bool(value: Optional[str], fallback: bool) -> bool:
        if value is None:
            return fallback
        normalized = value.strip().lower()
        return normalized in {"1", "true", "yes", "on"}

    async def is_registration_enabled(self) -> bool:
        value = await self._get_config_value("auth.allow_registration")
        return self._parse_bool(value, fallback=settings.allow_registration)

    async def is_linuxdo_login_enabled(self) -> bool:
        value = await self._get_config_value("auth.linuxdo_enabled")
        return self._parse_bool(value, fallback=settings.enable_linuxdo_login)

    async def _verify_turnstile(self, token: str, secret: Optional[str]) -> bool:
        if not secret:
            logger.warning("Turnstile secret key 未配置，跳过验证")
            return True
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                    data={"secret": secret, "response": token},
                )
                result = resp.json()
                if not result.get("success"):
                    logger.info("Turnstile 验证失败: %s", result.get("error-codes"))
                return result.get("success", False)
        except Exception as exc:
            logger.warning("Turnstile 验证请求异常: %s", exc)
            return False

    async def get_auth_options(self) -> AuthOptions:
        """聚合与认证相关的动态开关配置，便于前端一次性拉取。"""

        allow_registration = await self.is_registration_enabled()
        enable_linuxdo_login = await self.is_linuxdo_login_enabled()
        captcha_enabled = self._parse_bool(
            await self._get_config_value("captcha.enabled"), False
        )
        captcha_site_key = await self._get_config_value("captcha.site_key") if captcha_enabled else None
        return AuthOptions(
            allow_registration=allow_registration,
            enable_linuxdo_login=enable_linuxdo_login,
            enable_wechat_login=await self.is_wechat_login_enabled(),
            enable_google_login=await self.is_google_login_enabled(),
            enable_phone_login=await self.is_phone_login_enabled(),
            captcha_enabled=captcha_enabled,
            captcha_site_key=captcha_site_key,
        )

    def requires_password_reset(self, user: User | UserInDB) -> bool:
        if not user.is_admin:
            return False
        if user.username != settings.admin_default_username:
            return False
        hashed_password = getattr(user, "hashed_password", None)
        if not hashed_password:
            return False
        return verify_password(settings.admin_default_password, hashed_password)

    async def reset_password_with_code(self, email: str, code: str, new_password: str) -> None:
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该邮箱未注册")
        if not await self.verify_code(email, code, purpose="reset"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码无效或已过期")
        if len(new_password) < 8:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码至少需要8个字符")
        user.hashed_password = hash_password(new_password)
        await self.session.commit()

    async def change_password(self, username: str, old_password: str, new_password: str) -> None:
        user = await self.user_repo.get_by_username(username)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        if not verify_password(old_password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误")

        if verify_password(new_password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码不能与当前密码相同")

        if username == settings.admin_default_username and new_password == settings.admin_default_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码不能为默认密码")

        user.hashed_password = hash_password(new_password)
        await self.session.commit()
