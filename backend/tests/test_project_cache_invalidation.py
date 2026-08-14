"""章节状态变更必须作废项目详情缓存。

`GET /api/novels/{id}` 走 30 分钟 TTL 的序列化缓存，而生成路径是直接改 ORM 对象、
不经过 NovelService 的写路径，缓存不会自己失效。线上实测过一次：第 18 章正在生成
（单章接口返回 generating、SSE 正在吐字），项目接口却一直报 not_generated——
前端刷新后据此认为「没在生成」，既不提示后台仍在跑，也不拦重复点击。

这里钉住失效调用本身的契约：静默吞掉异常（缓存是加速手段，作废失败不能影响生成），
且真的把 key 删掉。
"""
import asyncio
from unittest.mock import AsyncMock, patch

from app.services.cache_service import CacheService


def test_invalidate_deletes_project_schema_key():
    calls = []

    async def _fake_delete(self, key):
        calls.append(key)
        return True

    with patch.object(CacheService, "delete", _fake_delete):
        asyncio.run(CacheService.invalidate_project_schema_safely("proj-1"))

    assert len(calls) == 1
    assert "proj-1" in calls[0]


def test_invalidate_swallows_failures():
    """Redis 挂了不能连累生成：这行代码跑在生成开工的关键路径上。"""

    async def _boom(self, key):
        raise RuntimeError("redis down")

    with patch.object(CacheService, "delete", _boom):
        asyncio.run(CacheService.invalidate_project_schema_safely("proj-2"))  # 不抛即通过


def test_generation_start_invalidates_cache():
    """编排器置 generating 之后必须调用失效——回归的是「刷新看到旧状态」那个真实故障。"""
    from app.services import pipeline_orchestrator as po

    source = __import__("inspect").getsource(po.PipelineOrchestrator.generate_chapter)
    marker = source.find('chapter.status = "generating"')
    assert marker > 0, "生成开工时置 generating 的那行不见了，测试需要跟着更新"
    following = source[marker : marker + 600]
    assert "invalidate_project_schema_safely" in following, (
        "置 generating 之后没有作废项目详情缓存，前端刷新会看到「未生成」"
    )
