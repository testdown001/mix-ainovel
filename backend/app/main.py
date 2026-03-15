# AIMETA P=FastAPI应用入口_装配路由依赖和生命周期管理|R=应用启动_路由注册_中间件配置|NR=不含业务逻辑实现|E=uvicorn_app.main:app|X=http|A=FastAPI_app实例|D=fastapi,uvicorn|S=net,db|RD=./README.ai
"""FastAPI 应用入口，负责装配路由、依赖与生命周期管理。"""

import logging
from logging.config import dictConfig
from logging.handlers import RotatingFileHandler
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.rate_limit_middleware import RateLimitMiddleware
from .db.init_db import init_db
from .services.prompt_service import PromptService
from .db.session import AsyncSessionLocal
from .api.routers import api_router


LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            },
            "verbose": {
                "format": "%(asctime)s [%(levelname)s] %(name)s %(funcName)s:%(lineno)d - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
            "file_app": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOG_DIR / "app.log"),
                "maxBytes": 10 * 1024 * 1024,
                "backupCount": 5,
                "encoding": "utf-8",
                "formatter": "verbose",
            },
            "file_llm": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOG_DIR / "llm.log"),
                "maxBytes": 20 * 1024 * 1024,
                "backupCount": 10,
                "encoding": "utf-8",
                "formatter": "verbose",
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
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置，生产环境建议改为具体域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 限流中间件（用户级请求限流）
app.add_middleware(RateLimitMiddleware)

app.include_router(api_router)


# 健康检查接口（用于 Docker 健康检查和监控）
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """健康检查接口，返回应用状态。"""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
    }
