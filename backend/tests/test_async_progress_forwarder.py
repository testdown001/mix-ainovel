"""异步任务路径"分阶段进度转发"回归测试。

历史问题：异步 worker 仅在生成前后报 4 个粗进度点，长生成期间静默，前端卡在
"正在生成章节..."像"转后台"。修复后 worker 把生成管线逐阶段 telemetry 实时转发为
任务进度。本测试锁定转发器：忽略非 stage 事件、阶段消息透传、进度单调不回退且封顶 79。
"""
import pytest

from app.api.routers.task_worker import _build_stage_progress_forwarder


class _FakeReporter:
    def __init__(self):
        self.calls: list[tuple[int, str, str]] = []

    async def report(self, progress, stage, message):
        self.calls.append((progress, stage, message))


@pytest.mark.asyncio
async def test_forwarder_ignores_non_stage_events():
    r = _FakeReporter()
    handler = _build_stage_progress_forwarder(r)
    await handler({"event": "text_delta", "delta": "abc"})  # 逐字草稿：异步不展示
    await handler({"event": "mission", "data": {}})          # 中间产物
    await handler("not a dict")                              # 非法载荷
    assert r.calls == []


@pytest.mark.asyncio
async def test_forwarder_reports_granular_stages_monotonic():
    r = _FakeReporter()
    handler = _build_stage_progress_forwarder(r)
    await handler({"event": "stage", "stage": "starting", "message": "开始生成章节"})
    await handler({"event": "stage", "stage": "build_generation_prompt", "message": "完成上下文组装，开始写作"})
    await handler({"event": "stage", "stage": "generate_versions", "message": "多版本生成中"})
    await handler({"event": "stage", "stage": "persist_versions", "message": "写入章节版本中"})

    pcts = [c[0] for c in r.calls]
    msgs = [c[2] for c in r.calls]
    # 每个阶段都上报，消息原样透传给前端阶段日志
    assert msgs == ["开始生成章节", "完成上下文组装，开始写作", "多版本生成中", "写入章节版本中"]
    # 进度单调不回退、封顶 79（80~100 留给后处理/收尾）
    assert pcts == sorted(pcts)
    assert all(20 <= p <= 79 for p in pcts)
    assert pcts[-1] == 79


@pytest.mark.asyncio
async def test_forwarder_progress_never_regresses():
    r = _FakeReporter()
    handler = _build_stage_progress_forwarder(r)
    await handler({"event": "stage", "stage": "generate_versions", "message": "多版本生成中"})  # ->58
    await handler({"event": "stage", "stage": "x", "message": "准备阶段"})  # 关键词"准备"->22，但不应回退
    assert r.calls[0][0] == 58
    assert r.calls[1][0] == 58
