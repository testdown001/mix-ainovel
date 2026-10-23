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

    async def _evidence(query, dimension):
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
