"""SPA 静态资源缓存策略回归测试。

线上现象（2026-08-01）：重建前端后，已打开的标签页点「设置」报
`TypeError: Failed to fetch dynamically imported module: .../SettingsView-DGkUEMLp.js`。
根因是 index.html 当时**不带任何 Cache-Control**，浏览器按启发式缓存住了它；
而 index.html 里写死了那次构建的 chunk 文件名，发版后这些文件已被删除 → 懒加载 404。

因此两条断言缺一不可：
- `assets/*`（文件名自带内容 hash）→ 可且应当永久缓存；
- 其余一切（尤其 index.html 与 SPA 路由回退）→ 必须每次回源校验。
"""
import re

# 刻意不 import app.main：它在导入时就 dictConfig 并设 propagate=False，会打坏
# 其它用例的 caplog（本文件首版正是这样一次性搞挂了 3 个无关测试）。
from app.core.spa_assets import apply_spa_cache_headers, is_spa_navigation_path as _is_spa_navigation_path


class _Resp:
    def __init__(self):
        self.headers: dict[str, str] = {}


def _cache_control(path: str) -> str:
    resp = _Resp()
    apply_spa_cache_headers(resp, path)
    return resp.headers["Cache-Control"]


def test_hashed_assets_are_immutable():
    """带 hash 的构建产物永久缓存——内容变了文件名就变，不存在过期问题。"""
    for path in (
        "assets/SettingsView-B1qIOOR-.js",
        "assets/index-abc123.css",
        "assets/logo-deadbeef.svg",
    ):
        cc = _cache_control(path)
        assert "immutable" in cc, (path, cc)
        assert "max-age=31536000" in cc, (path, cc)


def test_index_html_must_revalidate():
    """入口 HTML 绝不能被缓存住，否则发版后旧 index 会去要已删除的 chunk。"""
    cc = _cache_control("index.html")
    assert "no-cache" in cc
    assert "immutable" not in cc


def test_spa_fallback_paths_are_not_cached():
    """history 模式下这些路径回落 index.html，同样不能缓存。"""
    for path in ("", "settings", "home", "admin"):
        cc = _cache_control(path)
        assert "no-cache" in cc, (path, cc)
        assert "immutable" not in cc, (path, cc)


def test_root_and_known_prefixes_are_spa_navigations():
    """缓存策略依赖回退判定，一并锁住：settings 必须是 SPA 路由（本次事故的入口）。"""
    # 传入的是已去掉 query 的路径（StaticFiles 只拿 path 部分）
    assert _is_spa_navigation_path("/")
    assert _is_spa_navigation_path("/settings")
    assert _is_spa_navigation_path("/admin")
    assert _is_spa_navigation_path("/detail/123")
    # 公开分享阅读页：漏加白名单时游客拿到的是 404 JSON 而非页面（2026-08-14 上线时实发）
    assert _is_spa_navigation_path("/share/hnbxWgoZTtOF3KOmlcETAw")
    assert not _is_spa_navigation_path("/dyplay")


def test_asset_prefix_matches_vite_output_layout():
    """守卫：若 vite 输出目录不再是 assets/，immutable 规则会静默失效。

    仅当构建产物存在时校验（CI/开发机没有 dist 就跳过，不制造假失败）。
    """
    from pathlib import Path

    from app.core.config import settings

    assets_dir = Path(settings.frontend_dist_dir) / "assets"
    if not assets_dir.is_dir():
        return

    hashed = [p.name for p in assets_dir.glob("*.js")]
    if not hashed:
        return
    assert any(re.search(r"-[A-Za-z0-9_-]{6,}\.js$", name) for name in hashed), (
        f"assets/ 下未见带 hash 的 js，immutable 缓存不再安全: {hashed[:5]}"
    )
