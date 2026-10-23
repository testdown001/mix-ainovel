"""真实联网检索证据层（web_evidence_service）回归。

锁定：provider=none → 空串不发请求；jina 搜索 + 抓页拼成带来源的证据；serper 只有摘要；
网络失败软失败；维度检索在有证据时改用「只能依据资料」的提示词，并剥掉假工具调用行。
"""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app.models.system_config import SystemConfig
from app.services import web_evidence_service as wes
from app.services.web_search_service import WebSearchService, _strip_fake_tool_calls


async def _seed(session, **kv):
    for key, value in kv.items():
        session.add(SystemConfig(key=key.replace("__", "."), value=value))
    await session.commit()
    wes.invalidate_search_backend_cache()


def _transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_none_provider_returns_empty_without_requests(db_session):
    wes.invalidate_search_backend_cache()
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(200, json=[])

    client = httpx.AsyncClient(transport=_transport(handler))
    text = await wes.WebEvidenceService(db_session, client=client).gather("某书 目录")
    assert text == "" and calls == []


@pytest.mark.asyncio
async def test_jina_search_and_page_read(db_session):
    await _seed(db_session, search__provider="jina", search__api_key="jk", search__read_pages="1")
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.host == "s.jina.ai":
            assert request.headers["Authorization"] == "Bearer jk"
            return httpx.Response(200, json={"data": [
                {"title": "书页", "url": "https://www.qidian.com/book/1", "description": "已更新605章"},
                {"title": "书评", "url": "https://zhihu.com/q/2", "description": "节奏稳"},
                {"title": "无关", "url": "https://example.com/x", "description": ""},
            ]})
        if request.url.host == "r.jina.ai":
            return httpx.Response(200, text="第一卷 近海\n\n\n\n第二卷 远洋\n" + "正文" * 5000)
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=_transport(handler))
    text = await wes.WebEvidenceService(db_session, client=client).gather("渔猎八一 目录 分卷")
    assert "【联网检索结果】" in text and "[1] 书页 — https://www.qidian.com/book/1" in text
    assert "摘要：已更新605章" in text
    assert "【页面正文】https://www.qidian.com/book/1" in text and "第一卷 近海\n\n第二卷 远洋" in text
    assert len(text) < 8000  # 正文裁到 6000 字
    assert sum(1 for u in seen if "r.jina.ai" in u) == 1  # read_pages=1 只抓一页，且优先书页站点


@pytest.mark.asyncio
async def test_serper_search_snippets_only(db_session):
    await _seed(db_session, search__provider="serper", search__api_key="sk", search__max_results="2")

    def handler(request):
        assert request.url.host == "google.serper.dev" and request.headers["X-API-KEY"] == "sk"
        body = json.loads(request.content)
        assert body["num"] == 2 and body["hl"] == "zh-cn"
        return httpx.Response(200, json={"organic": [
            {"title": "a", "link": "https://a", "snippet": "sa"},
            {"title": "b", "link": "https://b", "snippet": "sb"},
            {"title": "c", "link": "https://c", "snippet": "sc"},
        ]})

    client = httpx.AsyncClient(transport=_transport(handler))
    text = await wes.WebEvidenceService(db_session, client=client).gather("某书")
    assert "[1] a — https://a" in text and "[2] b" in text and "[3]" not in text
    assert "【页面正文】" not in text


@pytest.mark.asyncio
async def test_network_failure_is_soft(db_session):
    await _seed(db_session, search__provider="jina", search__api_key="jk")

    def handler(request):
        raise httpx.ConnectError("boom")

    client = httpx.AsyncClient(transport=_transport(handler))
    assert await wes.WebEvidenceService(db_session, client=client).gather("某书") == ""


def test_strip_fake_tool_calls():
    raw = "invoke tool web_search with query is 番茄小说 《X》\n\n\n真实总结第一行\ncall tool search again\n第二行"
    assert _strip_fake_tool_calls(raw) == "真实总结第一行\n第二行"
    assert _strip_fake_tool_calls("invoke tool web_search with query x") == ""
    assert _strip_fake_tool_calls("") == ""


def test_dimension_search_uses_grounded_prompt_when_evidence_present():
    svc = WebSearchService.__new__(WebSearchService)

    class _Cache:
        def __init__(self):
            self.store = {}

        async def get(self, key):
            return self.store.get(key)

        async def set(self, key, value, ttl=None):
            self.store[key] = value

    svc.cache_service = _Cache()
    captured = {}

    async def _search(system_prompt, conversation_history, **_kw):
        captured["system"] = system_prompt
        captured["user"] = conversation_history[0]["content"]
        return "invoke tool web_search with query x\n依据 [1]，全书 605 章"

    async def _evidence(query, dimension, anchor=""):
        return f"【联网检索结果】查询：{query}\n[1] 书页 — https://q/1"

    svc.llm_service = SimpleNamespace(
        _resolve_search_llm_config=lambda: asyncio.sleep(0),
        get_search_llm_response=_search,
    )
    svc._gather_evidence = _evidence
    result = asyncio.run(svc.search_novel_dimensions(novel_name="某书", dimensions=["structure"]))
    assert "只能依据这些资料" in captured["system"]
    assert "【联网检索结果】" in captured["user"] and "目录 分卷" in captured["user"]
    assert result["structure"] == "依据 [1]，全书 605 章"  # 假工具调用行已剥掉


# ---------------------------------------------------------------- duckduckgo（零 key）

_DDG_HTML = """
<div class="result results_links">
  <h2 class="result__title"><a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.qidian.com%2Fbook%2F1047494729%2F&amp;rut=abc">渔猎八一，从近海到远洋 (<b>绑疯绳</b>)小说在线阅读-首发起点中文网</a></h2>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.qidian.com%2Fbook%2F1047494729%2F&amp;rut=abc"><b>绑疯绳</b>创作的都市小说，已更新606章，最新章节：606章：等出招再应对。</a>
</div>
<div class="result results_links">
  <h2 class="result__title"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fm.yunqi.qq.com%2Fchapter%2F57494788&amp;rut=def">全部章节—云起书院</a></h2>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fm.yunqi.qq.com%2Fchapter%2F57494788&amp;rut=def">更新时间：2026-10-20 最新章节：第601章</a>
</div>
<div class="result results_links">
  <h2 class="result__title"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fyunqi.qq.com%2Fdetail%2F57494788&amp;rut=ghi">在线阅读-云起书院官网</a></h2>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fyunqi.qq.com%2Fdetail%2F57494788&amp;rut=ghi">181万字 连载至607章</a>
</div>
<div class="result results_links">
  <h2 class="result__title"><a class="result__a" href="https://example.com/direct">直链结果</a></h2>
</div>
"""


def test_parse_duckduckgo_html_decodes_uddg_and_pairs_snippets():
    results = wes.parse_duckduckgo_html(_DDG_HTML, 10)
    assert [r["url"] for r in results] == [
        "https://www.qidian.com/book/1047494729/",
        "https://m.yunqi.qq.com/chapter/57494788",
        "https://yunqi.qq.com/detail/57494788",
        "https://example.com/direct",
    ]
    assert results[0]["title"].startswith("渔猎八一，从近海到远洋 (绑疯绳)")  # 标签剥掉、实体还原
    assert "已更新606章" in results[0]["snippet"]
    assert results[3]["snippet"] == ""
    assert len(wes.parse_duckduckgo_html(_DDG_HTML, 2)) == 2
    assert wes.parse_duckduckgo_html("<html><body>Just a moment</body></html>", 5) == []


def test_duckduckgo_is_configured_without_key_but_jina_is_not():
    assert wes.search_backend_configured({"provider": "duckduckgo", "api_key": ""})
    assert not wes.search_backend_configured({"provider": "jina", "api_key": ""})
    assert not wes.search_backend_configured({"provider": "none", "api_key": "x"})


def test_trim_page_markdown_drops_nav_keeps_chapter_list():
    raw = (
        "Title: 渔猎八一，从近海到远洋\n\nMarkdown Content:\n[](https://www.qidian.com/)\n\n[起点女生网](https://www.qdmm.com/)\n\n"
        "全部分类\n\n__\n\n*   [玄幻](https://www.qidian.com/xuanhuan/)\n*   [都市](https://www.qidian.com/dushi/)\n\n"
        "[排行](https://www.qidian.com/rank/)\n\n\n\n"
        "[都市](https://yunqi.qq.com/cate/20019)[都市生活](https://yunqi.qq.com/cate/20020)181万字\n"
        "连载至607章\n"
        "*   [第607章 607章：命运互换了？ 更新时间：2026-10-23 APP免费](https://yunqi.qq.com/read/57494788/607)\n"
        "*   [第606章 606章：等出招再应对 APP免费](https://yunqi.qq.com/read/57494788/606)\n"
    )
    trimmed = wes.trim_page_markdown(raw)
    assert "[玄幻]" not in trimmed and "[排行]" not in trimmed and "起点女生网" not in trimmed and "__" not in trimmed
    assert "Title: 渔猎八一，从近海到远洋" in trimmed
    assert "181万字" in trimmed and "连载至607章" in trimmed
    assert "第607章 607章：命运互换了？" in trimmed and "第606章" in trimmed
    assert "\n\n\n" not in trimmed


@pytest.mark.asyncio
async def test_duckduckgo_search_reads_pages_keyless_and_dedupes_hosts(db_session):
    await _seed(db_session, search__provider="duckduckgo", search__api_key="", search__read_pages="2")
    seen = []

    def handler(request):
        seen.append((str(request.url), request.headers.get("Authorization")))
        assert request.url.host == "r.jina.ai"
        target = str(request.url)[len("https://r.jina.ai/"):]
        if target.startswith("https://html.duckduckgo.com/html/?q="):
            assert request.headers["X-Return-Format"] == "html"
            return httpx.Response(200, text=_DDG_HTML)
        if "yunqi.qq.com" in target:
            return httpx.Response(200, text="*   [第607章 607章：命运互换了？](https://yunqi.qq.com/read/57494788/607)\n")
        if "qidian.com" in target:
            return httpx.Response(200, text="*   [玄幻](https://www.qidian.com/xuanhuan/)\n第一卷 近海 1-60章\n")
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=_transport(handler))
    text = await wes.WebEvidenceService(db_session, client=client).gather("渔猎八一，从近海到远洋 目录 分卷")
    assert "[1] 渔猎八一，从近海到远洋 (绑疯绳)" in text and "摘要：绑疯绳创作的都市小说，已更新606章" in text
    assert "【页面正文】https://www.qidian.com/book/1047494729/" in text and "第一卷 近海 1-60章" in text
    assert "[玄幻]" not in text  # 导航被裁
    # 两页：起点 + 云起（m.yunqi 与 yunqi 同站只抓一页），且全程无 Authorization
    page_urls = [u for u, _ in seen if "duckduckgo.com" not in u]
    assert len(page_urls) == 2 and any("yunqi.qq.com" in u for u in page_urls)
    assert all(auth is None for _, auth in seen)


@pytest.mark.asyncio
async def test_duckduckgo_retries_once_on_rate_limit(db_session, monkeypatch):
    await _seed(db_session, search__provider="duckduckgo", search__read_pages="0")
    monkeypatch.setattr(wes, "_READER_RETRY_DELAY", 0)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, text=_DDG_HTML)

    client = httpx.AsyncClient(transport=_transport(handler))
    text = await wes.WebEvidenceService(db_session, client=client).gather("渔猎八一")
    assert calls["n"] == 2 and "[1] 渔猎八一" in text


@pytest.mark.asyncio
async def test_duckduckgo_challenge_page_yields_empty(db_session):
    await _seed(db_session, search__provider="duckduckgo", search__read_pages="0")
    client = httpx.AsyncClient(transport=_transport(lambda r: httpx.Response(200, text="<html>anomaly</html>")))
    assert await wes.WebEvidenceService(db_session, client=client).gather("渔猎八一") == ""


# ---------------------------------------------------------------- 书名锚定过滤 / 目录页上限


def test_filter_results_by_anchor_drops_other_books_when_enough_anchored():
    book = "渔猎八一，从近海到远洋"
    results = [
        {"title": "渔猎八一，从近海到远洋 (绑疯绳)", "url": "https://a/1", "snippet": ""},
        {"title": "某刑侦文：看到案件证据的蜘蛛案例", "url": "https://b/2", "snippet": "主角能看到证据"},
        {"title": "云起书院", "url": "https://a/3", "snippet": "渔猎八一 更新时间 第601章"},  # 只写了逗号前半
        {"title": "无关", "url": "https://c/4", "snippet": "重生八一渔猎西北"},
        {"title": "全部章节", "url": "https://a/5", "snippet": "《渔猎八一，从近海到远洋》连载至607章"},
    ]
    kept = wes.filter_results_by_anchor(results, book)
    assert [r["url"] for r in kept] == ["https://a/1", "https://a/3", "https://a/5"]
    # 带书名的不足 3 条：只排序不丢弃
    few = wes.filter_results_by_anchor(results[:2], book)
    assert [r["url"] for r in few] == ["https://a/1", "https://b/2"]
    assert wes.filter_results_by_anchor(results, "") == results


@pytest.mark.asyncio
async def test_gather_passes_page_chars_cap(db_session):
    await _seed(db_session, search__provider="duckduckgo", search__read_pages="1")

    def handler(request):
        target = str(request.url)[len("https://r.jina.ai/"):]
        if target.startswith("https://html.duckduckgo.com"):
            return httpx.Response(200, text=_DDG_HTML)
        return httpx.Response(200, text="\n".join(f"*   [第{i}章 章名足够长不被裁掉](https://x/{i})" for i in range(1, 700)))

    client = httpx.AsyncClient(transport=_transport(handler))
    svc = wes.WebEvidenceService(db_session, client=client)
    small = await svc.gather("渔猎八一，从近海到远洋 目录", page_chars=3000)
    big = await svc.gather("渔猎八一，从近海到远洋 目录", page_chars=12000)
    assert len(big) > len(small) + 5000
