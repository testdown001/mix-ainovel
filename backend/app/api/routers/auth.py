# AIMETA P=认证API_登录注册和令牌管理|R=用户认证_令牌生成|NR=不含用户管理|E=route:POST_/api/auth/*|X=http|A=登录_注册_令牌|D=fastapi,jose|S=db|RD=./README.ai
import html
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.user import AuthOptions, Token, User, UserInDB, UserRegistration
from ...services.auth_service import AuthService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class PasswordResetRequest(BaseModel):
    email: str
    code: str
    new_password: str


class PhoneSendCodeRequest(BaseModel):
    phone: str


class PhoneLoginRequest(BaseModel):
    phone: str
    code: str


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    return AuthService(session)


def _oauth_callback_html(token: Token) -> str:
    """OAuth 回调统一页面：写入 token 到 localStorage 并跳首页。"""
    token_json = html.escape(token.model_dump_json())
    return f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head><meta charset=\"UTF-8\"><title>正在跳转</title></head>
<body>
    <p>正在跳转，请稍候...</p>
    <script>
        (function() {{
            const token = JSON.parse('{token_json}');
            try {{ window.localStorage.setItem('token', token.access_token); }}
            catch (err) {{ console.error('无法写入本地存储', err); }}
            window.location.replace('/');
        }})();
    </script>
</body>
</html>"""


@router.post("/send-code", status_code=204)
async def send_verification_code(email: str, service: AuthService = Depends(get_auth_service)):
    await service.send_verification_code(email, purpose="register")
    logger.info("向 %s 发送注册验证码", email)


@router.post("/send-reset-code", status_code=204)
async def send_password_reset_code(email: str, service: AuthService = Depends(get_auth_service)):
    """向邮箱发送密码重置验证码"""
    await service.send_verification_code(email, purpose="reset")
    logger.info("向 %s 发送密码重置验证码", email)


@router.post("/reset-password", status_code=204)
async def reset_password(payload: PasswordResetRequest, service: AuthService = Depends(get_auth_service)):
    """使用邮箱验证码重置密码"""
    await service.reset_password_with_code(payload.email, payload.code, payload.new_password)
    logger.info("用户 %s 密码重置成功", payload.email)


@router.get("/options", response_model=AuthOptions)
async def read_auth_options(service: AuthService = Depends(get_auth_service)):
    """读取认证功能开关，供前端动态渲染。"""
    options = await service.get_auth_options()
    return options


@router.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserRegistration, service: AuthService = Depends(get_auth_service)):
    user = await service.register_user(payload)
    logger.info("注册新用户：%s", user.username)
    return User.model_validate(user)


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), service: AuthService = Depends(get_auth_service)):
    user = await service.authenticate_user(form_data.username, form_data.password)
    must_change_password = service.requires_password_reset(user)
    token = await service.create_access_token(user, must_change_password=must_change_password)
    logger.info("用户 %s 登录成功，需改密=%s", form_data.username, must_change_password)
    return token


@router.get("/users/me", response_model=User)
async def read_current_user(current_user: UserInDB = Depends(get_current_user)):
    logger.debug("读取当前用户：%s", current_user.username)
    return current_user


@router.get("/linuxdo/login")
async def login_with_linuxdo(service: AuthService = Depends(get_auth_service)):
    if not await service.is_linuxdo_login_enabled():
        logger.warning("Linux.do 登录未启用")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未启用 Linux.do 登录")
    client_id = await service.get_config_value("linuxdo.client_id")
    redirect_uri = await service.get_config_value("linuxdo.redirect_uri")
    auth_url = await service.get_config_value("linuxdo.auth_url")
    if not all([client_id, redirect_uri, auth_url]):
        logger.error("Linux.do OAuth 参数未配置完整")
        raise HTTPException(status_code=500, detail="未配置 Linux.do OAuth 参数")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "user",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    logger.info("跳转 Linux.do 授权，client_id=%s", client_id)
    return RedirectResponse(url=f"{auth_url}?{query}")


@router.get("/linuxdo/register", response_class=HTMLResponse)
async def register_with_linuxdo(code: str, service: AuthService = Depends(get_auth_service)):
    token = await service.handle_linuxdo_callback(code)
    logger.info("Linux.do 授权回调成功")
    token_json = html.escape(token.model_dump_json())
    html_content = f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head><meta charset=\"UTF-8\"><title>正在跳转</title></head>
<body>
    <p>正在跳转，请稍候...</p>
    <script>
        (function() {{
            const token = JSON.parse('{token_json}');
            try {{
                window.localStorage.setItem('token', token.access_token);
            }} catch (err) {{
                console.error('无法写入本地存储', err);
            }}
            window.location.replace('/');
        }})();
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)


# ==================== 微信登录（网站应用扫码）====================

@router.get("/wechat/login")
async def login_with_wechat(service: AuthService = Depends(get_auth_service)):
    if not await service.is_wechat_login_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未启用微信登录")
    url = await service.build_wechat_authorize_url()
    return RedirectResponse(url=url)


@router.get("/wechat/callback", response_class=HTMLResponse)
async def wechat_callback(code: str, service: AuthService = Depends(get_auth_service)):
    token = await service.handle_wechat_callback(code)
    logger.info("微信授权回调成功")
    return HTMLResponse(content=_oauth_callback_html(token))


# ==================== 谷歌登录 ====================

@router.get("/google/login")
async def login_with_google(service: AuthService = Depends(get_auth_service)):
    if not await service.is_google_login_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未启用谷歌登录")
    client_id = await service.get_config_value("google.client_id")
    redirect_uri = await service.get_config_value("google.redirect_uri")
    if not all([client_id, redirect_uri]):
        raise HTTPException(status_code=500, detail="未配置 Google OAuth 参数")
    from urllib.parse import quote
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}&redirect_uri={quote(redirect_uri, safe='')}"
        "&response_type=code&scope=openid%20email%20profile&access_type=online&prompt=select_account"
    )
    return RedirectResponse(url=auth_url)


@router.get("/google/callback", response_class=HTMLResponse)
async def google_callback(code: str, service: AuthService = Depends(get_auth_service)):
    token = await service.handle_google_callback(code)
    logger.info("谷歌授权回调成功")
    return HTMLResponse(content=_oauth_callback_html(token))


# ==================== 手机号登录（验证码登录即注册）====================

@router.post("/phone/send-code", status_code=204)
async def send_phone_code(payload: PhoneSendCodeRequest, service: AuthService = Depends(get_auth_service)):
    await service.send_phone_code(payload.phone)


@router.post("/phone/login", response_model=Token)
async def phone_login(payload: PhoneLoginRequest, service: AuthService = Depends(get_auth_service)):
    token = await service.login_with_phone(payload.phone, payload.code)
    logger.info("手机号登录成功")
    return token
