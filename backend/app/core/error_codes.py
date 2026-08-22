# AIMETA P=领域错误码_稳定API错误响应|R=错误码枚举_结构化HTTP异常|NR=不含业务逻辑|E=DomainErrorCode_api_error|X=internal|A=错误契约|D=fastapi|S=none|RD=../../../../docs/standards/error-codes.md
"""M0 领域错误契约。

新接口使用结构化 detail，旧接口维持兼容并在被修改时逐步迁移。前端应按
``code`` 分支，不能解析面向作者展示的中文 ``message``。
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping

from fastapi import HTTPException


class DomainErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    FEATURE_NOT_AVAILABLE = "FEATURE_NOT_AVAILABLE"
    GENERATION_IN_PROGRESS = "GENERATION_IN_PROGRESS"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    VOLUME_NOT_FOUND = "VOLUME_NOT_FOUND"
    CHAPTER_NOT_FOUND = "CHAPTER_NOT_FOUND"
    CHAPTER_VERSION_NOT_FOUND = "CHAPTER_VERSION_NOT_FOUND"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    WORLD_STATE_SOURCE_MISMATCH = "WORLD_STATE_SOURCE_MISMATCH"
    WORLD_STATE_NOT_FOUND = "WORLD_STATE_NOT_FOUND"
    WORLD_STATE_INVALID = "WORLD_STATE_INVALID"
    DOMAIN_PERSISTENCE_FAILED = "DOMAIN_PERSISTENCE_FAILED"


def api_error(
    status_code: int,
    code: DomainErrorCode,
    message: str,
    *,
    meta: Mapping[str, Any] | None = None,
) -> HTTPException:
    """构造稳定、无敏感正文的 API 错误响应。"""
    detail: dict[str, Any] = {"code": str(code), "message": message}
    if meta:
        detail["meta"] = dict(meta)
    return HTTPException(status_code=status_code, detail=detail)
