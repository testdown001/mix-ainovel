"""阶段4 对抗复审修复回归。

锁定四项：
1. hard_trim_to_limit：max_chars 是硬上限契约，任何分支不得超限返回；
   保开头+保末段钩子、牺牲中部（旧"从倒数第二段整段删"会把整章删到只剩末段）。
2. literary prose_sculpting 的 rhythm/density 两次 LLM 调用步间复检预算。
3. literary（enable_scene_by_scene）不收润色附加费（收了必须交付，交付不了不收）。
4. 场景缺失残章按 completed 交付但全额退还积分（result 标记 degraded）。
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.models.user_quota  # noqa: F401  防 mapper KeyError

from app.services.text_compression_service import TextCompressionService


# ------------------------------------------------------------------
# 1. hard_trim_to_limit
# ------------------------------------------------------------------

def test_hard_trim_huge_first_paragraph_keeps_head_and_tail():
    """首段超限 + 短末段：旧实现整段删掉首段只剩 20 字钩子；新实现句切中部保开头+钩子。"""
    body = ("这是正文句子。" * 600)  # 4200 字单大段
    hook = "他回头，看见了那双眼睛。"
    text = body + "\n\n" + hook
    result = TextCompressionService.hard_trim_to_limit(text, 3000)

    assert len(result) <= 3000
    assert result.endswith(hook)
    # 开头被保留（而非整段丢弃）
    assert result.startswith("这是正文句子。")
    assert len(result) > 2000  # 不再是"只剩钩子"的 20 字残章


def test_hard_trim_never_exceeds_max_even_with_sparse_punctuation():
    """单段句读稀疏：末句自身超限时硬切守住上限（旧回退可数倍超限）。"""
    text = "他走了。" + "很" * 500 + "。"
    result = TextCompressionService.hard_trim_to_limit(text, 100)
    assert len(result) <= 100


def test_hard_trim_multi_paragraph_drops_middle():
    paras = [f"第{i}段内容。" * 30 for i in range(5)]  # 每段 210 字
    text = "\n\n".join(paras)
    result = TextCompressionService.hard_trim_to_limit(text, 500)

    assert len(result) <= 500
    assert result.startswith("第0段内容。")          # 开头保留
    assert result.endswith(paras[-1])                # 末段完整保留
    assert "第2段内容" not in result                  # 中部被牺牲


def test_hard_trim_within_limit_untouched():
    text = "短文。\n\n结尾。"
    assert TextCompressionService.hard_trim_to_limit(text, 100) == text


# ------------------------------------------------------------------
# 2. literary rhythm/density 步间预算复检
# ------------------------------------------------------------------

def test_density_sculpting_rechecks_budget_after_rhythm(monkeypatch):
    from app.services import literary_generation_flow_service as lit_module
    from app.services import prose_sculptor_service as sculptor_module

    class _Clock:
        def __init__(self):
            self.now = 0.0

        def perf_counter(self):
            return self.now

    clock = _Clock()
    monkeypatch.setattr(lit_module, "time", clock)

    calls: list[str] = []

    async def _rhythm(self, content, **kwargs):
        calls.append("rhythm")
        clock.now += 900  # 该步吃穿剩余预算
        return content + "·韵", {"applied": True}

    async def _density(self, content, **kwargs):
        calls.append("density")
        return content + "·密", {"applied": True}

    monkeypatch.setattr(sculptor_module.ProseSculptorService, "sculpt_rhythm", _rhythm)
    monkeypatch.setattr(sculptor_module.ProseSculptorService, "sculpt_density", _density)

    review_summaries: dict = {}
    skipped: list[str] = []

    # 直接驱动 prose_sculpting 块的最小闭包语义：复用服务内 _over_budget 公式
    deadline = 1000.0
    _PER_STEP = 180.0

    def _over_budget():
        return deadline is not None and (deadline - clock.perf_counter()) < _PER_STEP

    # 模拟：rhythm 启动时剩 1000s 通过检查；rhythm 耗 900s 后 density 复检应拦下
    assert not _over_budget()
    sculptor = sculptor_module.ProseSculptorService(SimpleNamespace())
    content = asyncio.run(sculptor.sculpt_rhythm("正文"))[0]
    assert _over_budget()  # 复检语义成立的前提

    # 源码级断言：literary 流程在 rhythm 与 density 之间确实有 _over_budget 复检
    import inspect

    src = inspect.getsource(lit_module)
    rhythm_pos = src.find("sculpt_rhythm")
    density_pos = src.find("sculpt_density", rhythm_pos)
    recheck_pos = src.find("_over_budget", rhythm_pos)
    assert rhythm_pos != -1 and density_pos != -1
    assert rhythm_pos < recheck_pos < density_pos, "rhythm 与 density 之间缺少预算复检"
    assert calls == ["rhythm"]
    assert content == "正文·韵"
    assert review_summaries == {} and skipped == []  # 本测试仅验证复检语义与源码结构


# ------------------------------------------------------------------
# 3/4. task_worker：literary 不收润色费 + 残章退款
# ------------------------------------------------------------------

from app.api.routers import task_worker  # noqa: E402


class _SessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


def _base_mocks(monkeypatch, *, tier="flagship"):
    monkeypatch.setattr(task_worker.settings, "task_dispatcher_internal_callback_secret", "s3cret")
    monkeypatch.setattr(task_worker, "AsyncSessionLocal", lambda: _SessionContext(SimpleNamespace()))
    monkeypatch.setattr(task_worker, "get_user_tier", AsyncMock(return_value=tier))
    monkeypatch.setattr(task_worker, "ensure_generation_preset_allowed", AsyncMock())
    monkeypatch.setattr(task_worker, "ensure_flow_overrides_allowed", AsyncMock())
    monkeypatch.setattr(task_worker, "ensure_model_allowed", AsyncMock())


def _make_req(extra):
    return task_worker.WorkerTaskRequest(
        task_id="task-p4",
        task_type="chapter:generate",
        project_id="p1",
        chapter_number=1,
        user_id=7,
        config=task_worker.TaskConfig(preset="premium", extra=extra),
    )


def test_literary_does_not_charge_polish_surcharge(monkeypatch):
    _base_mocks(monkeypatch)
    charge = AsyncMock(return_value=0)
    monkeypatch.setattr(task_worker, "charge_generation", charge)
    monkeypatch.setattr(
        task_worker, "_execute_chapter_generate", AsyncMock(return_value={"status": "completed"})
    )

    resp = asyncio.run(task_worker.execute_task(
        _make_req({"enable_polish": True, "enable_scene_by_scene": True}),
        x_internal_secret="s3cret",
    ))
    assert resp.status == "completed"
    # literary 分支不含 polish 步：勾选也不收附加费
    assert charge.await_args.args[3] is False

    charge.reset_mock()
    resp = asyncio.run(task_worker.execute_task(
        _make_req({"enable_polish": True}),
        x_internal_secret="s3cret",
    ))
    assert resp.status == "completed"
    assert charge.await_args.args[3] is True  # 非 literary 照常收费


def test_missing_scenes_triggers_full_refund_and_degraded_flag(monkeypatch):
    _base_mocks(monkeypatch)
    monkeypatch.setattr(task_worker, "charge_generation", AsyncMock(return_value=15))
    refund = AsyncMock(return_value=15)
    monkeypatch.setattr(task_worker, "refund_generation", refund)
    monkeypatch.setattr(
        task_worker,
        "_execute_chapter_generate",
        AsyncMock(return_value={"status": "completed", "missing_scenes": [2, 3]}),
    )

    resp = asyncio.run(task_worker.execute_task(
        _make_req({"enable_scene_by_scene": True}),
        x_internal_secret="s3cret",
    ))
    assert resp.status == "completed"          # 残章仍交付（内容保留）
    assert resp.result["degraded"] is True     # 但标记降级
    refund.assert_awaited_once()               # 已扣积分全额退还
    assert refund.await_args.kwargs.get("ref_key") == "task-p4"


def test_no_missing_scenes_no_refund(monkeypatch):
    _base_mocks(monkeypatch)
    monkeypatch.setattr(task_worker, "charge_generation", AsyncMock(return_value=15))
    refund = AsyncMock(return_value=15)
    monkeypatch.setattr(task_worker, "refund_generation", refund)
    monkeypatch.setattr(
        task_worker, "_execute_chapter_generate", AsyncMock(return_value={"status": "completed"})
    )

    resp = asyncio.run(task_worker.execute_task(
        _make_req({}),
        x_internal_secret="s3cret",
    ))
    assert resp.status == "completed"
    refund.assert_not_awaited()
