# AIMETA P=真实联网检索证据层|R=搜索API适配(jina/serper)_页面抓取_证据文本组装|NR=不含LLM总结|E=WebEvidenceService|X=net|A=检索基础设施|D=httpx,config_service|S=net|RD=./README.ai
"""真实联网检索：给「搜索通道」的 LLM 喂真实网页证据，而不是让它凭记忆编。

背景（2026-10-23 生产实测）：所谓搜索通道只是一次普通 chat completion，没有任何联网工具。
模型对名著靠记忆答，对新书/冷门书要么写「资料未提及」，要么把 `invoke tool web_search ...`
当成正文输出。一本起点在连载、605 章的书被判定「该标题不存在」。

这里做的事很窄：按 SystemConfig `search.provider` 调一个搜索 API，拿回标题/URL/摘要，
可选再抓前几个结果页的正文（r.jina.ai），拼成带来源的证据文本。总结仍交给搜索通道的
LLM，但 prompt 改为「只能依据以下资料」。

- provider=duckduckgo（默认，零 key）：DuckDuckGo 的 HTML 结果页经 r.jina.ai 渲染后解析
  （服务器直连 DDG 会吃到 202 挑战页；无 key 的 r.jina.ai 有 ~20 RPM 的限速，所以这里
  给阅读器调用加了并发闸门和一次重试）。页面正文同样用无 key 的 r.jina.ai 抓。
  2026-10-23 从生产机实测：一本 607 章的起点连载，第一条结果就是书页，摘要里带作者和章数；
  云起/创世的镜像页正文里有完整章节目录。
- provider=jina：s.jina.ai 搜索（需要 key）+ r.jina.ai 抓页；provider=serper：Google 摘要。
- provider=none：返回空串，调用方退回旧行为（模型记忆），并在配置体检里告警。
- 任何网络/解析失败都返回空串并记 warning：证据是增益，不能让分析挂掉。
"""
from __future__ import annotations

import asyncio
import html as html_lib
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote, urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

PROVIDER_KEY = "search.provider"
API_KEY_KEY = "search.api_key"
MAX_RESULTS_KEY = "search.max_results"
READ_PAGES_KEY = "search.read_pages"

SUPPORTED_PROVIDERS = ("none", "duckduckgo", "jina", "serper")
KEYLESS_PROVIDERS = ("duckduckgo",)
PAGE_READING_PROVIDERS = ("jina", "duckduckgo")
DEFAULT_PROVIDER = "duckduckgo"
_DEFAULT_MAX_RESULTS = 8
_DEFAULT_READ_PAGES = 2
_PAGE_CHAR_CAP = 6000
_SNIPPET_CHAR_CAP = 400
_HTTP_TIMEOUT = 25.0
_READER_TIMEOUT = 45.0
_CONFIG_TTL_SECONDS = 60
_READER_RETRY_DELAY = 2.0
_RETRYABLE_STATUS = (422, 429, 500, 502, 503, 504)

# 抓正文时优先的站点（书页/目录页信息密度高）；其余站点只用摘要
_PREFERRED_PAGE_HOSTS = (
    "qidian.com", "yunqi.qq.com", "chuangshi.qq.com", "fanqienovel.com", "read.qq.com",
    "readnovel.com", "zongheng.com", "17k.com", "qimao.com", "ciweimao.com", "faloo.com",
    "rongshuxia.com", "hongxiu.com", "jjwxc.net", "zhihu.com", "douban.com", "lkong.com", "baidu.com",
)

_config_cache: Dict[str, Any] = {"at": 0.0, "value": None}
# 无 key 的 r.jina.ai 按 IP 限速（约 20 RPM）；六个维度并行检索时不能把它打爆
_reader_gate = asyncio.Semaphore(3)


def _cache_key(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip())[:200]


async def resolve_search_backend_config(session: AsyncSession) -> Dict[str, Any]:
    """读 SystemConfig（60s 进程缓存）：provider/api_key/max_results/read_pages。"""
    now = time.monotonic()
    cached = _config_cache.get("value")
    if cached is not None and now - float(_config_cache.get("at") or 0) < _CONFIG_TTL_SECONDS:
        return cached
    # 键不存在/读不到 → none（测试与裸库不许偷偷联网）；新库由 system_config_defaults 种成 duckduckgo
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
    provider = config.get("provider")
    if provider in KEYLESS_PROVIDERS:
        return True
    return provider in ("jina", "serper") and bool(config.get("api_key"))


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
        if pages_wanted and config["provider"] in PAGE_READING_PROVIDERS:
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
        if provider == "duckduckgo":
            return await self._search_duckduckgo(query, config)
        if provider == "jina":
            return await self._search_jina(query, config)
        if provider == "serper":
            return await self._search_serper(query, config)
        return []

    async def _search_duckduckgo(self, query: str, config: Dict[str, Any]) -> List[Dict[str, str]]:
        """DDG 的 HTML 结果页经 r.jina.ai（无 key 可用）取回原始 HTML 再解析。

        直连 html.duckduckgo.com 从服务器出去只会拿到 202 挑战页；经阅读器取则是正常结果页。
        `X-Return-Format: html` 要的是原始 HTML——result__a / result__snippet 比 markdown 稳定得多。
        """
        target = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        headers = {"Accept": "text/plain", "X-Return-Format": "html"}
        if config.get("api_key"):
            headers["Authorization"] = f"Bearer {config['api_key']}"
        response = await self._reader_get(f"https://r.jina.ai/{target}", headers)
        return parse_duckduckgo_html(response.text or "", config["max_results"])

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
        """r.jina.ai 抓正文（markdown），失败返回空串。有 key 带 key，没 key 走限速的匿名额度。"""
        headers = {"Accept": "text/plain", "X-Return-Format": "markdown"}
        if config.get("api_key"):
            headers["Authorization"] = f"Bearer {config['api_key']}"
        try:
            response = await self._reader_get(f"https://r.jina.ai/{url}", headers)
            text = response.text or ""
        except Exception as exc:  # noqa: BLE001
            logger.debug("抓页失败 %s: %s", url, exc)
            return ""
        return trim_page_markdown(text)[:_PAGE_CHAR_CAP]

    async def _reader_get(self, url: str, headers: Dict[str, str]) -> httpx.Response:
        """r.jina.ai 调用：并发闸门 + 对限速/瞬时错误重试一次。"""
        async with _reader_gate:
            async with self._client_ctx() as client:
                response = await client.get(url, headers=headers, timeout=_READER_TIMEOUT)
                if response.status_code in _RETRYABLE_STATUS:
                    logger.debug("阅读器返回 %s，%.0fs 后重试一次: %s", response.status_code, _READER_RETRY_DELAY, url)
                    await asyncio.sleep(_READER_RETRY_DELAY)
                    response = await client.get(url, headers=headers, timeout=_READER_TIMEOUT)
                response.raise_for_status()
                return response

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


_DDG_RESULT_RE = re.compile(
    r'<a[^>]*class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>', re.IGNORECASE | re.DOTALL,
)
_DDG_SNIPPET_RE = re.compile(
    r'<a[^>]*class="result__snippet"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<snippet>.*?)</a>', re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _ddg_target_url(href: str) -> str:
    """DDG 结果链接是 //duckduckgo.com/l/?uddg=<真实URL>&rut=…，解出真实 URL。"""
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return target.strip()
    return href


def _html_text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(_TAG_RE.sub("", fragment))).strip()


def parse_duckduckgo_html(raw: str, max_results: int) -> List[Dict[str, str]]:
    """解析 html.duckduckgo.com 结果页；无结果/挑战页返回 []。"""
    snippets: Dict[str, str] = {}
    for match in _DDG_SNIPPET_RE.finditer(raw):
        url = _ddg_target_url(match.group("href"))
        if url and url not in snippets:
            snippets[url] = _html_text(match.group("snippet"))[:_SNIPPET_CHAR_CAP]
    results: List[Dict[str, str]] = []
    seen: set[str] = set()
    for match in _DDG_RESULT_RE.finditer(raw):
        url = _ddg_target_url(match.group("href"))
        if not url.startswith("http") or url in seen:
            continue
        seen.add(url)
        results.append({"title": _html_text(match.group("title")), "url": url, "snippet": snippets.get(url, "")})
        if len(results) >= max_results:
            break
    return results


_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")


def trim_page_markdown(text: str) -> str:
    """去掉阅读器输出里的导航噪音，让 6000 字的上限留给正文和目录。

    书站页面（起点/云起）经 r.jina.ai 出来前 2-3KB 全是分类导航：`*   [玄幻](…)` 一行一个，
    `X-Remove-Selector` 对它们不起作用（不在语义标签里）。规则：把链接折成可见文字后，
    只剩 ≤4 个字的行丢掉；纯链接（链接之外没有正文）且 ≤8 个字的行也丢掉（「作家专区」「起点女生网」）；
    章节目录行（「第607章 命运互换了？」）虽是纯链接但可见文字长，会保留。
    """
    def _squash(s: str) -> str:
        s = re.sub(r"https?://\S+", "", s)
        return re.sub(r"[\s*\-_•|>#\[\]()]+", "", s)

    kept: List[str] = []
    for line in (text or "").splitlines():
        if not line.strip():
            kept.append("")
            continue
        visible = _squash(_LINK_RE.sub(lambda m: m.group(1), line))
        plain = _squash(_LINK_RE.sub("", line))
        if len(visible) <= 4 or (not plain and len(visible) <= 8):
            continue
        kept.append(line.rstrip())
    joined = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", joined).strip()


def _page_host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[2:] if host.startswith("m.") else host


def _pick_pages(results: List[Dict[str, str]], count: int) -> List[Dict[str, str]]:
    """优先书站页，且同一站只抓一页（m.yunqi 和 yunqi 是同一份目录）。"""
    preferred = [r for r in results if any(host in r["url"] for host in _PREFERRED_PAGE_HOSTS)]
    rest = [r for r in results if r not in preferred]
    picked: List[Dict[str, str]] = []
    hosts: set[str] = set()
    for item in preferred + rest:
        host = _page_host(item["url"])
        if host in hosts:
            continue
        hosts.add(host)
        picked.append(item)
        if len(picked) >= count:
            break
    return picked


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
