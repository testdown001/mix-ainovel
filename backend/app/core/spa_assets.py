# AIMETA P=SPA静态资源策略_路由回退与缓存头|R=前端dist服务策略|NR=不含挂载逻辑_不含FastAPI依赖|E=is_spa_navigation_path,apply_spa_cache_headers|X=internal|A=纯函数|D=none|S=none|RD=./README.ai
"""前端 dist 的服务策略：哪些路径算 SPA 导航、各类资源怎么缓存。

刻意独立成模块（而非留在 main.py）：这两个是无依赖的纯函数，
而 `app.main` 在**导入时**就执行 dictConfig 并给多个 logger 设 propagate=False，
测试里一旦 import 它就会打坏其它用例的 caplog。
"""
from __future__ import annotations

# 与 frontend/src/router/index.ts 顶层路由保持一致：仅这些前缀(及根路径)在 history 模式下
# 未命中静态文件时才回退 index.html；其余未知路径(爬虫/垃圾 URL，如 /dyplay、/m/xijupian)
# 返回 404，不再被 SPA 兜底统统应答 200（污染日志、白吃资源）。新增前端顶层路由时同步此处。
SPA_ROUTE_PREFIXES = frozenset({
    "home", "workspace", "inspiration", "detail", "novel",
    "login", "register", "forgot-password", "admin",
    "settings", "pricing", "terms", "privacy",
})

# Vite 的构建产物目录；该目录下文件名自带内容 hash
_HASHED_ASSET_PREFIX = "assets/"

_IMMUTABLE = "public, max-age=31536000, immutable"
_ALWAYS_REVALIDATE = "no-cache, must-revalidate"


def is_spa_navigation_path(path: str) -> bool:
    """请求路径是否对应前端 SPA 路由（决定未命中静态文件时是否回退 index.html）。"""
    cleaned = path.strip("/")
    if not cleaned:
        return True  # 根路径
    return cleaned.split("/", 1)[0] in SPA_ROUTE_PREFIXES


def cache_control_for(path: str) -> str:
    """按路径决定 Cache-Control。

    Vite 把 chunk 输出成 assets/Name-<hash>.js，文件名即内容指纹 → 可永久缓存。
    但 index.html **写死了本次构建的 chunk 文件名**，一旦被浏览器缓存住，下次发版后
    旧 index 会去请求已被删除的 chunk，切路由时报
    「Failed to fetch dynamically imported module」（2026-08-01 线上实发）。
    所以 index.html 必须每次回源校验（etag 命中仍返回 304，不增加带宽）。
    """
    return _IMMUTABLE if path.startswith(_HASHED_ASSET_PREFIX) else _ALWAYS_REVALIDATE


def apply_spa_cache_headers(response, path: str) -> None:
    """就地写入 Cache-Control 头。"""
    response.headers["Cache-Control"] = cache_control_for(path)
