# AIMETA P=真实联网检索证据层|R=搜索API适配(jina/serper)_页面抓取_证据文本组装|NR=不含LLM总结|E=WebEvidenceService|X=net|A=检索基础设施|D=httpx,config_service|S=net|RD=./README.ai
"""真实联网检索：给「搜索通道」的 LLM 喂真实网页证据，而不是让它凭记忆编。

背景（2026-10-23 生产实测）：所谓搜索通道只是一次普通 chat completion，没有任何联网工具。
模型对名著靠记忆答，对新书/冷门书要么写「资料未提及」，要么把 `invoke tool web_search ...`
当成正文输出。一本起点在连载、605 章的书被判定「该标题不存在」。

这里做的事很窄：按 SystemConfig `search.provider` 调一个搜索 API，拿回标题/URL/摘要，
可选再抓前几个结果页的正文（r.jina.ai），拼成带来源的证据文本。总结仍交给搜索通道的
LLM，但 prompt 改为「只能依据以下资料」。

- provider=none（默认）：返回空串，调用方退回旧行为（模型记忆），并在配置体检里告警。
- 任何网络/解析失败都返回空串并记 warning：证据是增益，不能让分析挂掉。
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

PROVIDER_KEY = "search.provider"
API_KEY_KEY = "search.api_key"
MAX_RESULTS_KEY = "search.max_results"
READ_PAGES_KEY = "search.read_pages"

SUPPORTED_PROVIDERS = ("none", "jina", "serper")
_DEFAULT_MAX_RESULTS = 8
_DEFAULT_READ_PAGES = 2
_PAGE_CHAR_CAP = 6000
_SNIPPET_CHAR_CAP = 400
_HTTP_TIMEOUT = 25.0
_CONFIG_TTL_SECONDS = 60

# 抓正文时优先的站点（书页/目录页信息密度高）；其余站点只用摘要
_PREFERRED_PAGE_HOSTS = (
    "qidian.com", "fanqienovel.com", "read.qq.com", "readnovel.com", "rongshuxia.com",
    "hongxiu.com", "jjwxc.net", "zhihu.com", "douban.com", "lkong.com", "baidu.com",
)

_config_cache: Dict[str, Any] = {"at": 0.0, "value": None}


def _cache_key(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip())[:200]


async def resolve_search_backend_config(session: AsyncSession) -> Dict[str, Any]:
    """读 SystemConfig（60s 进程缓存）：provider/api_key/max_results/read_pages。"""
    now = time.monotonic()
    cached = _config_cache.get("value")
    if cached is not None and now - float(_config_cache.get("at") or 0) < _CONFIG_TTL_SECONDS:
        return cached
    config: Dict[str, Any] = {
        "provider": "none", "api_key": "", "max_results": _DEFAULT_MAX_RESULTS, "read_pages": _DEFAULT_READ_PAGES,
    }
    try:
        from .config_service import ConfigService

        service = ConfigService(session)

        async def _get(key: str) -> Optional[str]:
            record = await service.get_config(key)
            return (record.value or "").strip() if record is not None else None

        provider = (await _get(PROVIDER_KEY) or "none").lower()
        config["provider"] = provider if provider in SUPPORTED_PROVIDERS else "none"
        config["api_key"] = await _get(API_KEY_KEY) or ""
        try:
            config["max_results"] = max(1, min(10, int(await _get(MAX_RESULTS_KEY) or _DEFAULT_MAX_RESULTS)))
        except ValueError:
            pass
        try:
            config["read_pages"] = max(0, min(4, int(await _get(READ_PAGES_KEY) or _DEFAULT_READ_PAGES)))
        except ValueError:
            pass
    except Exception as exc:  # noqa: BLE001 - 配置读取失败按未配置处理
        logger.debug("搜索后端配置读取失败，按 provider=none: %s", exc)
    _config_cache["at"] = now
    _config_cache["value"] = config
    return config


def invalidate_search_backend_cache() -> None:
    _config_cache["at"] = 0.0
    _config_cache["value"] = None


def search_backend_configured(config: Dict[str, Any]) -> bool:
    return config.get("provider") in ("jina", "serper") and bool(config.get("api_key"))


class WebEvidenceService:
    def __init__(self, session: AsyncSession, *, client: Optional[httpx.AsyncClient] = None):
        self.session = session
        self._client = client

    # ------------------------------------------------------------------
    # 入口
    # ------------------------------------------------------------------
    async def gather(self, query: str, *, read_pages: Optional[int] = None) -> str:
        """检索 + 可选抓页 → 带来源的证据文本；未配置/失败返回空串。"""
        config = await resolve_search_backend_config(self.session)
        if not search_backend_configured(config):
            return ""
        try:
            results = await self._search(query, config)
        except Exception as exc:  # noqa: BLE001
            logger.warning("联网检索失败(provider=%s): %s", config.get("provider"), exc)
            return ""
        if not results:
            return ""
        pages_wanted = config["read_pages"] if read_pages is None else max(0, min(4, read_pages))
        page_texts: Dict[str, str] = {}
        if pages_wanted and config["provider"] == "jina":
            for item in _pick_pages(results, pages_wanted):
                text = await self._read_page(item["url"], config)
                if text:
                    page_texts[item["url"]] = text
        return _format_evidence(query, results, page_texts)

    # ------------------------------------------------------------------
    # 搜索 API 适配
    # ------------------------------------------------------------------
    async def _search(self, query: str, config: Dict[str, Any]) -> List[Dict[str, str]]:
        provider = config["provider"]
        if provider == "jina":
            return await self._search_jina(query, config)
        if provider == "serper":
            return await self._search_serper(query, config)
        return []

    async def _search_jina(self, query: str, config: Dict[str, Any]) -> List[Dict[str, str]]:
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Accept": "application/json",
            "X-Respond-With": "no-content",  # 只要标题/URL/摘要，正文按需另抓
        }
        async with self._client_ctx() as client:
            response = await client.get(
                f"https://s.jina.ai/?q={quote(query)}&gl=cn&hl=zh-cn", headers=headers, timeout=_HTTP_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        items = payload.get("data") if isinstance(payload, dict) else payload
        results: List[Dict[str, str]] = []
        for item in items or []:
            if not isinstance(item, dict) or not item.get("url"):
                continue
            results.append({
                "title": str(item.get("title") or "").strip(),
                "url": str(item.get("url") or "").strip(),
                "snippet": str(item.get("description") or item.get("content") or "").strip()[:_SNIPPET_CHAR_CAP],
            })
            if len(results) >= config["max_results"]:
                break
        return results

    async def _search_serper(self, query: str, config: Dict[str, Any]) -> List[Dict[str, str]]:
        headers = {"X-API-KEY": config["api_key"], "Content-Type": "application/json"}
        body = {"q": query, "gl": "cn", "hl": "zh-cn", "num": config["max_results"]}
        async with self._client_ctx() as client:
            response = await client.post("https://google.serper.dev/search", headers=headers, json=body, timeout=_HTTP_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
        results: List[Dict[str, str]] = []
        for item in (payload.get("organic") if isinstance(payload, dict) else None) or []:
            if not isinstance(item, dict) or not item.get("link"):
                continue
            results.append({
                "title": str(item.get("title") or "").strip(),
                "url": str(item.get("link") or "").strip(),
                "snippet": str(item.get("snippet") or "").strip()[:_SNIPPET_CHAR_CAP],
            })
            if len(results) >= config["max_results"]:
                break
        return results

    async def _read_page(self, url: str, config: Dict[str, Any]) -> str:
        """r.jina.ai 抓正文（markdown），失败返回空串。"""
        headers = {"Authorization": f"Bearer {config['api_key']}", "Accept": "text/plain", "X-Return-Format": "text"}
        try:
            async with self._client_ctx() as client:
                response = await client.get(f"https://r.jina.ai/{url}", headers=headers, timeout=_HTTP_TIMEOUT)
                response.raise_for_status()
                text = response.text or ""
        except Exception as exc:  # noqa: BLE001
            logger.debug("抓页失败 %s: %s", url, exc)
            return ""
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text[:_PAGE_CHAR_CAP]

    def _client_ctx(self):
        if self._client is not None:
            return _NoCloseCtx(self._client)
        return httpx.AsyncClient(follow_redirects=True)


class _NoCloseCtx:
    """测试注入的 client 不随每次调用关闭。"""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self.client

    async def __aexit__(self, *args: Any) -> bool:
        return False


def _pick_pages(results: List[Dict[str, str]], count: int) -> List[Dict[str, str]]:
    preferred = [r for r in results if any(host in r["url"] for host in _PREFERRED_PAGE_HOSTS)]
    rest = [r for r in results if r not in preferred]
    return (preferred + rest)[:count]


def _format_evidence(query: str, results: List[Dict[str, str]], pages: Dict[str, str]) -> str:
    lines = [f"【联网检索结果】查询：{query}（共 {len(results)} 条，以下为真实抓取内容，只能依据这些资料总结）"]
    for index, item in enumerate(results, start=1):
        lines.append(f"[{index}] {item['title'] or '(无标题)'} — {item['url']}")
        if item.get("snippet"):
            lines.append(f"    摘要：{item['snippet']}")
    for url, text in pages.items():
        lines.append("")
        lines.append(f"【页面正文】{url}")
        lines.append(text)
    return "\n".join(lines)
