# 安全漏洞修复报告

## 修复日期
2026-06-01

## 已完成修复

### ✅ 立即修复（已完成）

#### 1. 创建 .gitignore 防止敏感信息泄露
**状态**: ✅ 已完成  
**文件**: `backend/.gitignore`

**修复内容**:
- 创建了完整的 `.gitignore` 文件，包含 `.env`、日志、缓存等敏感文件
- 验证确认 `.env` 文件从未被提交到 Git 历史，密钥安全

**影响**: 防止未来敏感配置文件被意外提交到版本控制

---

#### 2. 修复限流中间件 JWT 解析错误
**状态**: ✅ 已完成  
**文件**: `backend/app/core/rate_limit_middleware.py`

**问题**: 
- 原代码尝试将 JWT subject（username 字符串）转换为 int，导致 ValueError
- 所有已认证用户被错误地降级到 IP 限流（30 req/min vs 60 req/min）

**修复内容**:
```python
# 修改前
def _extract_user_id(self, request: Request) -> Optional[int]:
    return int(payload.get("sub", 0)) or None  # ❌ ValueError

# 修改后
def _extract_user_identifier(self, request: Request) -> Optional[str]:
    sub = payload.get("sub")
    return str(sub) if sub else None  # ✅ 正确处理字符串
```

**影响**: 已认证用户现在可以正确享受更高的限流配额

---

### ✅ 短期修复（已完成）

#### 3. JWT 改用 user_id 作为 subject
**状态**: ✅ 已完成  
**文件**: 
- `backend/app/core/security.py`
- `backend/app/core/dependencies.py`
- `backend/app/services/auth_service.py`

**问题**: 
- 使用 username 作为 JWT subject，用户改名后旧 token 仍有效但指向错误用户
- 如果允许用户名重用，可能导致权限混乱

**修复内容**:
```python
# security.py - 支持 user_id 或 username（向后兼容）
def create_access_token(subject: int | str, ...):
    to_encode = {"sub": str(subject), ...}

# auth_service.py - 新 token 使用 user_id
token = create_access_token(user.id, extra_claims=payload)

# dependencies.py - 兼容新旧格式
try:
    user_id = int(subject)
    user = await repo.get(id=user_id)  # 新格式
except (ValueError, TypeError):
    user = await repo.get_by_username(subject)  # 旧格式（向后兼容）
```

**影响**: 
- 新登录用户使用 user_id，不受用户名变更影响
- 旧 token 仍然有效（向后兼容）
- 用户名可以安全修改

---

#### 4. 分离注册和密码重置验证码
**状态**: ✅ 已完成  
**文件**: 
- `backend/app/services/auth_service.py`
- `backend/app/api/routers/auth.py`

**问题**: 
- 注册验证码和密码重置验证码共享同一个缓存
- 攻击者可以请求注册验证码，然后用它重置任意邮箱的密码

**修复内容**:
```python
# 分离缓存键
cache_key = f"{purpose}:{email}"  # "register:user@example.com" 或 "reset:user@example.com"

# 密码重置前验证用户存在（防止邮箱枚举）
if purpose == "reset":
    user = await self.user_repo.get_by_email(email)
    if not user:
        return  # 静默失败，不抛出异常

# 路由层明确指定 purpose
await service.send_verification_code(email, purpose="register")
await service.send_verification_code(email, purpose="reset")
```

**影响**: 
- 注册和密码重置验证码完全隔离
- 防止邮箱枚举攻击

---

#### 5. 将验证码存储迁移到 Redis
**状态**: ✅ 已完成  
**文件**: `backend/app/services/auth_service.py`

**问题**: 
- 验证码存储在内存字典中，多实例部署时失效
- 无法防止分布式暴力破解

**修复内容**:
```python
# 优先使用 Redis
redis = await self._get_redis()
if redis:
    await redis.setex(f"verify_code:{cache_key}", 300, code)  # 5分钟过期
    await redis.setex(rate_limit_key, 60, str(now))  # 1分钟限流
else:
    # 降级到内存缓存（向后兼容）
    self._verification_cache[cache_key] = (code, now + 300)
```

**特性**:
- ✅ 支持多实例部署
- ✅ 自动降级到内存缓存（Redis 不可用时）
- ✅ 分布式限流保护
- ✅ 自动过期清理

**影响**: 
- 支持水平扩展
- 更强的暴力破解防护

---

## 测试建议

### 1. JWT 功能测试
```bash
# 测试新用户登录（使用 user_id）
curl -X POST http://localhost:8000/api/auth/token \
  -d "username=testuser&password=password123"

# 验证 token 可以正常使用
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/auth/users/me
```

### 2. 验证码功能测试
```bash
# 测试注册验证码
curl -X POST "http://localhost:8000/api/auth/send-code?email=test@example.com"

# 测试密码重置验证码
curl -X POST "http://localhost:8000/api/auth/send-reset-code?email=test@example.com"

# 验证两者不能互相使用
```

### 3. Redis 降级测试
```bash
# 停止 Redis
docker stop redis

# 验证验证码功能仍然工作（使用内存缓存）
curl -X POST "http://localhost:8000/api/auth/send-code?email=test@example.com"

# 重启 Redis
docker start redis
```

### 4. 限流测试
```bash
# 测试已认证用户限流（60 req/min）
for i in {1..65}; do
  curl -H "Authorization: Bearer <token>" \
    http://localhost:8000/api/novels
done

# 应该在第 61 次请求时返回 429
```

---

## 向后兼容性

所有修复都保持了向后兼容：

1. **JWT**: 旧 token（username）仍然有效，新 token 使用 user_id
2. **验证码**: Redis 不可用时自动降级到内存缓存
3. **限流**: 中间件正确处理新旧两种 JWT 格式

---

## 部署注意事项

### 环境变量检查
确保 `.env` 文件包含：
```bash
# Redis 配置（必需）
REDIS_URL=redis://localhost:6379/0

# JWT 密钥（必需）
SECRET_KEY=<强随机字符串>

# 数据库密码（必需）
MYSQL_PASSWORD=<安全密码>
```

### 依赖检查
```bash
cd backend
pip install -r requirements.txt
# 确保 redis==5.0.7 已安装
```

### 重启服务
```bash
# 重启后端服务以应用更改
docker-compose restart backend

# 或者
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

---

## 后续建议（中期优化）

以下问题已识别但未在本次修复：

1. **CORS 配置过于宽松** - 建议限制 `allow_methods` 和 `allow_headers`
2. **支付回调缺少幂等性保护** - 建议添加订单状态检查
3. **缺少请求体大小限制** - 建议添加 10MB 限制
4. **生产环境缺少 HTTPS 强制重定向** - 建议添加 HTTPSRedirectMiddleware

详细信息请参考完整的安全审计报告。

---

## 修复作者
Claude Opus 4.8 (AI Assistant)

## 审核状态
⏳ 待人工审核
