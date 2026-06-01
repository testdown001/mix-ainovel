"""灵感缪斯·跨界素材发现服务测试（搜索通道，优雅降级）。"""
import asyncio

from fastapi import HTTPException

from app.services.muse_material_service import MuseMaterialService


def _make_service(search_impl):
    svc = MuseMaterialService.__new__(MuseMaterialService)  # 跳过 __init__
    class _LLM:
        get_search_llm_response = staticmethod(search_impl)
    svc.llm_service = _LLM()
    return svc


def test_discover_returns_material_on_success():
    async def _ok(**kwargs):
        return "<think>略</think>【冷门历史】xxx\n『嫁接钩子』yyy"
    svc = _make_service(_ok)
    out = asyncio.run(svc.discover_cross_domain_material(seed_topic="一个守墓人的故事", user_id=1))
    assert out is not None
    assert "嫁接钩子" in out
    assert "<think>" not in out  # 思考标签已剔除


def test_empty_seed_returns_none_without_calling():
    called = {"n": 0}
    async def _spy(**kwargs):
        called["n"] += 1
        return "x"
    svc = _make_service(_spy)
    out = asyncio.run(svc.discover_cross_domain_material(seed_topic="  ", user_id=1))
    assert out is None
    assert called["n"] == 0  # 空种子不触发检索


def test_unconfigured_search_model_degrades_to_none():
    async def _503(**kwargs):
        raise HTTPException(status_code=503, detail="未配置搜索模型")
    svc = _make_service(_503)
    out = asyncio.run(svc.discover_cross_domain_material(seed_topic="点子", user_id=1))
    assert out is None  # 优雅跳过，不抛


def test_generic_exception_degrades_to_none():
    async def _boom(**kwargs):
        raise RuntimeError("network down")
    svc = _make_service(_boom)
    out = asyncio.run(svc.discover_cross_domain_material(seed_topic="点子", user_id=1))
    assert out is None


def test_blank_result_returns_none():
    async def _blank(**kwargs):
        return "   \n  "
    svc = _make_service(_blank)
    out = asyncio.run(svc.discover_cross_domain_material(seed_topic="点子", user_id=1))
    assert out is None
