# AIMETA P=用户模式_用户和认证请求响应|R=用户结构_令牌结构|NR=不含业务逻辑|E=UserSchema_TokenSchema|X=internal|A=Pydantic模式|D=pydantic|S=none|RD=./README.ai
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional


class UserBase(BaseModel):
    """用户基础数据结构，供多处复用。"""

    username: str = Field(..., description="用户名")
    email: Optional[EmailStr] = Field(default=None, description="邮箱，可选")


class UserCreate(UserBase):
    """注册时使用的模型。"""

    password: str = Field(..., min_length=6, description="明文密码")


class UserUpdate(BaseModel):
    """用户信息修改模型。"""

    email: Optional[EmailStr] = Field(default=None, description="邮箱")
    password: Optional[str] = Field(default=None, min_length=6, description="新密码")


class UserCreateAdmin(UserCreate):
    """管理员创建用户模型。"""

    is_admin: bool = Field(default=False, description="是否为管理员")
    is_active: bool = Field(default=True, description="是否激活")


class UserUpdateAdmin(UserUpdate):
    """管理员更新用户信息模型。"""

    username: Optional[str] = Field(default=None, description="用户名")
    is_admin: Optional[bool] = Field(default=None, description="是否为管理员")
    is_active: Optional[bool] = Field(default=None, description="是否激活")


class User(UserBase):
    """对外暴露的用户信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="用户主键")
    is_admin: bool = Field(default=False, description="是否为管理员")
    is_active: bool = Field(default=True, description="是否激活")
    must_change_password: bool = Field(default=False, description="是否需要强制修改密码")
    plan_tier: Optional[str] = Field(default="free", description="订阅档位: free/creator/flagship")
    effective_tier: Optional[str] = Field(default="free", description="实际生效档位（考虑Premium失效回退）")


class UserInDB(User):
    """数据库内部使用的模型，包含哈希后的密码。"""

    hashed_password: str


class Token(BaseModel):
    """登录成功后返回的访问令牌。"""

    access_token: str
    token_type: str = "bearer"
    must_change_password: bool = Field(default=False, description="是否需要强制修改密码")


class TokenPayload(BaseModel):
    """JWT 负载信息。"""

    sub: str
    is_admin: bool = False


class UserRegistration(UserCreate):
    """注册接口需要的字段，包含邮箱验证码。"""

    verification_code: str = Field(..., min_length=4, max_length=10, description="邮箱验证码")
    captcha_token: Optional[str] = Field(None, description="Turnstile 人机验证 token")
    invite_code: Optional[str] = Field(None, max_length=32, description="邀请码（选填，注册双方各得积分）")


class PasswordChangeRequest(BaseModel):
    """管理员修改密码请求模型。"""

    old_password: str = Field(..., min_length=6, description="当前密码")
    new_password: str = Field(..., min_length=8, description="新密码")


class AuthOptions(BaseModel):
    """认证相关开关信息，供前端动态控制功能。"""

    allow_registration: bool = Field(..., description="是否允许开放用户注册")
    enable_linuxdo_login: bool = Field(..., description="是否启用 Linux.do 登录")
    enable_wechat_login: bool = Field(False, description="是否启用微信登录")
    enable_google_login: bool = Field(False, description="是否启用谷歌登录")
    enable_phone_login: bool = Field(False, description="是否启用手机号登录")
    captcha_enabled: bool = Field(False, description="是否启用注册人机验证")
    captcha_site_key: Optional[str] = Field(None, description="Turnstile Site Key")
