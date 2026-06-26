# AIMETA P=FastAPI应用入口_装配路由依赖和生命周期管理|R=应用启动_路由注册_中间件配置|NR=不含业务逻辑实现|E=uvicorn_app.main:app|X=http|A=FastAPI_app实例|D=fastapi,uvicorn|S=net,db|RD=./README.ai
"""FastAPI 应用入口，负责装配路由、依赖与生命周期管理。"""

import logging
from logging.config import dictConfig
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .core.config import settings
from .core.rate_limit_middleware import RateLimitMiddleware
from .core.request_id_middleware import RequestIdFilter, RequestIdMiddleware
from .core.request_size_limit_middleware import RequestSizeLimitMiddleware
from .core.security_headers_middleware import SecurityHeadersMiddleware
from .db.init_db import init_db
from .services.prompt_service import PromptService
from .utils.rerank_utils import get_rerank_runtime_status
from .db.session import AsyncSessionLocal
from .api.routers import api_router

logger = logging.getLogger(__name__)

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s - %(message)s",
            },
            "verbose": {
                "format": "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s %(funcName)s:%(lineno)d - %(message)s",
            },
        },
        "filters": {
            "request_id": {
                "()": "app.core.request_id_middleware.RequestIdFilter",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "filters": ["request_id"],
            },
            "file_app": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOG_DIR / "app.log"),
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 5,
                "encoding": "utf-8",
                "formatter": "verbose",
                "filters": ["request_id"],
            },
            "file_llm": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOG_DIR / "llm.log"),
                "maxBytes": 20 * 1024 * 1024,
                "backupCount": 10,
                "encoding": "utf-8",
                "formatter": "verbose",
                "filters": ["request_id"],
            },
            "file_trace": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOG_DIR / "trace.log"),
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 5,
                "encoding": "utf-8",
                "formatter": "verbose",
                "filters": ["request_id"],
            },
        },
        "loggers": {
            "backend": {
                "level": settings.logging_level,
                "handlers": ["console", "file_app"],
                "propagate": False,
            },
            "app": {
                "level": settings.logging_level,
                "handlers": ["console", "file_app"],
                "propagate": False,
            },
            "backend.app": {
                "level": settings.logging_level,
                "handlers": ["console", "file_app"],
                "propagate": False,
            },
            "backend.api": {
                "level": settings.logging_level,
                "handlers": ["console", "file_app"],
                "propagate": False,
            },
            "backend.services": {
                "level": settings.logging_level,
                "handlers": ["console", "file_app"],
                "propagate": False,
            },
            "app.utils.llm_tool": {
                "level": "DEBUG",
                "handlers": ["console", "file_llm"],
                "propagate": False,
            },
            "app.services.llm_service": {
                "level": "DEBUG",
                "handlers": ["console", "file_llm"],
                "propagate": False,
            },
            "arboris.trace": {
                "level": "INFO",
                "handlers": ["file_trace"],
                "propagate": False,
            },
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console", "file_app"],
        },
    }
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时初始化数据库，并预热提示词缓存
    await init_db()
    async with AsyncSessionLocal() as session:
        prompt_service = PromptService(session)
        await prompt_service.preload()
    rerank_status = await get_rerank_runtime_status()
    logger.info(
        "Reranker 启动状态: enabled=%s model=%s source=%s api_url=%s api_key_configured=%s integration=%s",
        rerank_status["enabled"],
        rerank_status["model"],
        rerank_status["config_source"],
        rerank_status["api_url"] or "none",
        rerank_status["api_key_configured"],
        "chapter_generation_rag",
    )
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="1.0.0",
    lifespan=lifespan,
)

# HTTPS 强制重定向（仅生产环境，且未显式关闭）
# TLS 通常在 nginx/LB 层终止，后端经 X-Forwarded-Proto 感知协议；
# 内网 HTTP 部署或反代未透传协议时，设 FORCE_HTTPS_REDIRECT=false 关闭以免重定向死循环。
if not settings.debug and settings.force_https_redirect:
    app.add_middleware(HTTPSRedirectMiddleware)

# CORS 配置，通过 CORS_ORIGINS 环境变量控制允许的来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "User-Agent",
        "DNT",
        "Cache-Control",
        "X-Requested-With",
    ],
    expose_headers=["Content-Length", "X-Request-ID"],
    max_age=600,  # 预检请求缓存 10 分钟
)

# API 限流中间件（IP + 用户级请求限流）
app.add_middleware(RateLimitMiddleware)

# 请求体大小限制（10MB）
app.add_middleware(RequestSizeLimitMiddleware, max_size=10 * 1024 * 1024)

# 安全响应头中间件
app.add_middleware(SecurityHeadersMiddleware)

# Request ID 中间件（最外层，确保所有日志可关联）
app.add_middleware(RequestIdMiddleware)

app.include_router(api_router)


# 健康检查接口（用于 Docker 健康检查和监控）
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """健康检查接口，检查数据库连接后返回应用状态。"""
    checks = {}

    # 检查数据库连接
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())

    payload = {
        "status": "healthy" if all_ok else "unhealthy",
        "app": settings.app_name,
        "version": "1.0.0",
        "checks": checks,
    }

    if not all_ok:
        return JSONResponse(content=payload, status_code=503)
    return payload


# ----- 前端静态资源服务（SPA） -----
# 当存在前端构建产物（dist）时，由 FastAPI 直接服务前端页面与静态资源，
# 未命中的非 API 路径回退到 index.html 以支持 Vue Router 的 history 模式。
# 该挂载必须在所有 API 路由与 /health 注册之后，确保接口优先匹配；
# dist 缺失（开发模式）时静默跳过，不影响接口与测试。
# 与 frontend/src/router/index.ts 顶层路由保持一致：仅这些前缀(及根路径)在 history 模式下
# 未命中静态文件时才回退 index.html；其余未知路径(爬虫/垃圾 URL，如 /dyplay、/m/xijupian)
# 返回 404，不再被 SPA 兜底统统应答 200（污染日志、白吃资源）。新增前端顶层路由时同步此处。
_SPA_ROUTE_PREFIXES = frozenset({
    "home", "workspace", "inspiration", "detail", "novel",
    "login", "register", "forgot-password", "admin",
    "settings", "pricing", "terms", "privacy",
})


def _is_spa_navigation_path(path: str) -> bool:
    """请求路径是否对应前端 SPA 路由（决定未命中静态文件时是否回退 index.html）。"""
    cleaned = path.strip("/")
    if not cleaned:
        return True  # 根路径
    return cleaned.split("/", 1)[0] in _SPA_ROUTE_PREFIXES


_frontend_dist = Path(settings.frontend_dist_dir)
if _frontend_dist.is_dir() and (_frontend_dist / "index.html").is_file():
    from fastapi.staticfiles import StaticFiles
    from starlette.exceptions import HTTPException as StarletteHTTPException

    class _SPAStaticFiles(StaticFiles):
        """history 模式 SPA：静态文件未命中时回退到 index.html；保留 /api 路径的 404 语义。"""

        async def get_response(self, path, scope):
            try:
                return await super().get_response(path, scope)
            except StarletteHTTPException as exc:
                if (
                    exc.status_code == 404
                    and not path.startswith("api")
                    and _is_spa_navigation_path(path)
                ):
                    return await super().get_response("index.html", scope)
                raise

    app.mount("/", _SPAStaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
    logger.info("前端静态资源已挂载：%s", _frontend_dist)
else:
    logger.info("未发现前端构建产物(%s)，跳过静态挂载（开发模式下属正常）", _frontend_dist)
